import axios from 'axios'

// Configure axios defaults
const api = axios.create({
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Rate limiting storage
const RATE_LIMIT_KEY = 'cecilia-api-rate-limit'

class SubscriptionAPI {
  constructor() {
    this.rateLimitInfo = this.loadRateLimit()
  }

  loadRateLimit() {
    try {
      const stored = localStorage.getItem(RATE_LIMIT_KEY)
      if (stored) {
        const data = JSON.parse(stored)
        return {
          remaining: data.remaining || 5,
          resetTime: data.resetTime ? new Date(data.resetTime) : null,
          lastRequestTime: data.lastRequestTime ? new Date(data.lastRequestTime) : null
        }
      }
    } catch (e) {
      console.warn('Failed to load rate limit info:', e)
    }
    return {
      remaining: 5,
      resetTime: null,
      lastRequestTime: null
    }
  }

  saveRateLimit() {
    try {
      localStorage.setItem(RATE_LIMIT_KEY, JSON.stringify({
        remaining: this.rateLimitInfo.remaining,
        resetTime: this.rateLimitInfo.resetTime?.toISOString(),
        lastRequestTime: this.rateLimitInfo.lastRequestTime?.toISOString()
      }))
    } catch (e) {
      console.warn('Failed to save rate limit info:', e)
    }
  }

  checkRateLimit() {
    const now = new Date()

    // Reset rate limit if reset time has passed
    if (this.rateLimitInfo.resetTime && now >= this.rateLimitInfo.resetTime) {
      this.rateLimitInfo.remaining = 5
      this.rateLimitInfo.resetTime = null
      this.saveRateLimit()
    }

    // Check if rate limited
    if (this.rateLimitInfo.remaining <= 0) {
      const resetTime = this.rateLimitInfo.resetTime
      if (resetTime && now < resetTime) {
        const minutes = Math.ceil((resetTime - now) / (1000 * 60))
        throw new Error(`Rate limit exceeded. Please try again in ${minutes} minutes.`)
      }
    }

    // Check minimum interval between requests (prevent spam)
    if (this.rateLimitInfo.lastRequestTime) {
      const timeSinceLastRequest = now - this.rateLimitInfo.lastRequestTime
      const minInterval = 2000 // 2 seconds minimum between requests

      if (timeSinceLastRequest < minInterval) {
        throw new Error('Please wait a moment before making another request.')
      }
    }

    return true
  }

  updateRateLimit() {
    const now = new Date()
    this.rateLimitInfo.remaining -= 1
    this.rateLimitInfo.lastRequestTime = now

    if (!this.rateLimitInfo.resetTime) {
      this.rateLimitInfo.resetTime = new Date(now.getTime() + 15 * 60 * 1000) // 15 minutes
    }

    this.saveRateLimit()
  }

  /**
   * Create a new email subscription
   * @param {string} email - User's email address
   * @param {Array<string>} topics - Array of ArXiv topic IDs (e.g., ['cs.ai', 'cs.cv'])
   * @returns {Promise<Object>} API response
   */
  async createSubscription(email, topics) {
    try {
      // Check rate limit
      this.checkRateLimit()

      // Validate input
      if (!email || !topics || topics.length < 5) {
        throw new Error('Email and at least 5 topics are required')
      }

      // Validate email format
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
      if (!emailRegex.test(email)) {
        throw new Error('Please enter a valid email address')
      }

      // Make API request
      const response = await api.post('/api/subscription/create', {
        email: email.trim().toLowerCase(),
        topics: topics
      })

      // Update rate limit on successful request
      this.updateRateLimit()

      return {
        success: true,
        data: response.data,
        verificationRequired: response.data.verification_required || false,
        sessionToken: response.data.session_token
      }

    } catch (error) {
      if (error.response?.status === 429) {
        // Server-side rate limiting
        this.rateLimitInfo.remaining = 0
        this.rateLimitInfo.resetTime = new Date(Date.now() + 15 * 60 * 1000)
        this.saveRateLimit()
        throw new Error('Too many requests. Please try again in 15 minutes.')
      } else if (error.response?.status === 400) {
        throw new Error(error.response.data.error || 'Invalid request. Please check your input.')
      } else if (error.response?.status === 409) {
        throw new Error('This email is already subscribed to some of these topics.')
      } else if (error.code === 'ECONNABORTED') {
        throw new Error('Request timeout. Please check your internet connection and try again.')
      } else if (error.response?.status >= 500) {
        throw new Error('Server error. Please try again later.')
      } else if (error.message.includes('Rate limit') || error.message.includes('wait')) {
        throw error // Re-throw rate limit errors from our local check
      } else {
        console.error('Subscription API error:', error)
        throw new Error('Failed to create subscription. Please try again later.')
      }
    }
  }

  /**
   * Verify email with 6-digit code
   * @param {string} sessionToken - Session token from create subscription
   * @param {string} verificationCode - 6-digit verification code
   * @returns {Promise<Object>} API response
   */
  async verifyEmail(sessionToken, verificationCode) {
    try {
      // Validate input
      if (!sessionToken || !verificationCode) {
        throw new Error('Session token and verification code are required')
      }

      // Validate verification code format (6 digits)
      const codeRegex = /^\d{6}$/
      if (!codeRegex.test(verificationCode)) {
        throw new Error('Please enter a valid 6-digit verification code')
      }

      // Make API request
      const response = await api.post('/api/subscription/verify', {
        session_token: sessionToken,
        verification_code: verificationCode.trim()
      })

      return {
        success: true,
        data: response.data,
        message: response.data.message || 'Email verified and subscription activated successfully!'
      }

    } catch (error) {
      if (error.response?.status === 400) {
        throw new Error(error.response.data.error || 'Invalid verification code or expired session.')
      } else if (error.response?.status === 404) {
        throw new Error('Verification session not found or expired. Please start over.')
      } else if (error.response?.status === 429) {
        throw new Error('Too many verification attempts. Please try again later.')
      } else if (error.code === 'ECONNABORTED') {
        throw new Error('Request timeout. Please try again.')
      } else if (error.response?.status >= 500) {
        throw new Error('Server error. Please try again later.')
      } else if (error.message.includes('digit')) {
        throw error // Re-throw validation errors
      } else {
        console.error('Verification API error:', error)
        throw new Error('Verification failed. Please try again.')
      }
    }
  }

  /**
   * Resend verification code
   * @param {string} sessionToken - Session token from create subscription
   * @returns {Promise<Object>} API response
   */
  async resendVerificationCode(sessionToken) {
    try {
      // Check rate limit for resend (more restrictive)
      this.checkRateLimit()

      if (!sessionToken) {
        throw new Error('Session token is required')
      }

      const response = await api.post('/api/subscription/resend', {
        session_token: sessionToken
      })

      // Update rate limit on successful request
      this.updateRateLimit()

      return {
        success: true,
        data: response.data,
        message: response.data.message || 'Verification code sent successfully!'
      }

    } catch (error) {
      if (error.response?.status === 400) {
        throw new Error(error.response.data.error || 'Invalid session or request.')
      } else if (error.response?.status === 404) {
        throw new Error('Verification session not found or expired. Please start over.')
      } else if (error.response?.status === 429) {
        // Server-side rate limiting for resend
        this.rateLimitInfo.remaining = 0
        this.rateLimitInfo.resetTime = new Date(Date.now() + 15 * 60 * 1000)
        this.saveRateLimit()
        throw new Error('Too many resend attempts. Please try again in 15 minutes.')
      } else if (error.code === 'ECONNABORTED') {
        throw new Error('Request timeout. Please try again.')
      } else if (error.message.includes('Rate limit') || error.message.includes('wait')) {
        throw error // Re-throw rate limit errors
      } else {
        console.error('Resend API error:', error)
        throw new Error('Failed to resend verification code. Please try again.')
      }
    }
  }

  /**
   * Get rate limit information
   * @returns {Object} Rate limit info
   */
  getRateLimit() {
    const now = new Date()

    // Reset if time has passed
    if (this.rateLimitInfo.resetTime && now >= this.rateLimitInfo.resetTime) {
      this.rateLimitInfo.remaining = 5
      this.rateLimitInfo.resetTime = null
    }

    return {
      remaining: this.rateLimitInfo.remaining,
      resetTime: this.rateLimitInfo.resetTime,
      canMakeRequest: this.rateLimitInfo.remaining > 0
    }
  }
}

// Export a singleton instance
export default new SubscriptionAPI()
