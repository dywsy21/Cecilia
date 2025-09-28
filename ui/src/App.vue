<!-- filepath: c:\Users\Admin\Desktop\Cecilia\ui\src\App.vue -->
<template>
  <div class="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50">
    <!-- Header -->
    <header class="bg-white shadow-sm border-b border-gray-200">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-3">
            <div class="flex-shrink-0">
              <div class="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center">
                <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.746 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path>
                </svg>
              </div>
            </div>
            <div>
              <h1 class="text-2xl font-bold text-gray-900">Cecilia Research Assistant</h1>
              <p class="text-sm text-gray-600">ArXiv Paper Subscription Service</p>
            </div>
          </div>
          <div class="hidden md:flex items-center space-x-4">
            <div class="flex items-center space-x-2 text-sm text-gray-500">
              <div class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
              <span>AI-Powered Summaries</span>
            </div>
            <div class="flex items-center space-x-2 text-sm text-gray-500">
              <div class="w-2 h-2 bg-blue-500 rounded-full"></div>
              <span>Daily Delivery</span>
            </div>
          </div>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <!-- Introduction Section -->
      <div class="text-center mb-12">
        <h2 class="text-3xl font-bold text-gray-900 mb-4">
          Subscribe to Daily ArXiv Paper Summaries
        </h2>
        <p class="text-lg text-gray-600 max-w-2xl mx-auto mb-8">
          Get AI-powered summaries of the latest research papers delivered to your inbox every morning.
          Select your research interests and stay updated with cutting-edge developments.
        </p>
        <div class="flex justify-center space-x-8 text-sm text-gray-500">
          <div class="flex items-center space-x-2">
            <CheckIcon class="w-5 h-5 text-green-500" />
            <span>Free Service</span>
          </div>
          <div class="flex items-center space-x-2">
            <CheckIcon class="w-5 h-5 text-green-500" />
            <span>Daily at 7:00 AM</span>
          </div>
          <div class="flex items-center space-x-2">
            <CheckIcon class="w-5 h-5 text-green-500" />
            <span>AI Summaries in Chinese</span>
          </div>
          <div class="flex items-center space-x-2">
            <CheckIcon class="w-5 h-5 text-green-500" />
            <span>PDF Attachments</span>
          </div>
        </div>
      </div>

      <!-- Subscription Form -->
      <div class="bg-white rounded-2xl shadow-xl border border-gray-200 overflow-hidden">
        <div class="px-8 py-6 bg-gradient-to-r from-indigo-500 to-purple-600">
          <h3 class="text-xl font-semibold text-white">
            {{ verificationStep ? 'Verify Your Email' : 'Create Your Subscription' }}
          </h3>
          <p class="text-indigo-100 mt-1">
            {{ verificationStep ? 'Enter the 6-digit code sent to your email' : 'Select at least 5 research topics to get started' }}
          </p>
        </div>

        <div class="p-8">
          <!-- Verification Step -->
          <div v-if="verificationStep" class="space-y-6">
            <!-- Email Confirmation Display -->
            <div class="bg-green-50 border border-green-200 rounded-lg p-4">
              <div class="flex items-center space-x-2">
                <CheckIcon class="w-5 h-5 text-green-500" />
                <span class="text-green-800 font-medium">Verification email sent to {{ email }}</span>
              </div>
              <p class="text-green-700 text-sm mt-1">Please check your inbox and enter the 6-digit verification code below.</p>
            </div>

            <!-- Verification Code Input -->
            <div>
              <label for="verificationCode" class="block text-sm font-medium text-gray-700 mb-2">
                Verification Code *
              </label>
              <div class="relative">
                <input
                  id="verificationCode"
                  v-model="verificationCode"
                  type="text"
                  maxlength="6"
                  pattern="[0-9]{6}"
                  :disabled="isVerifying"
                  :class="[
                    'block w-full px-4 py-3 text-center text-2xl font-mono tracking-wider rounded-lg border-2 transition-colors duration-200',
                    'focus:outline-none focus:ring-0',
                    verificationError ? 'border-red-300 focus:border-red-500' :
                    'border-gray-300 focus:border-indigo-500'
                  ]"
                  placeholder="123456"
                  @input="handleVerificationInput"
                  @keypress="handleKeyPress"
                />
              </div>
              <p v-if="verificationError" class="mt-1 text-sm text-red-600">{{ verificationError }}</p>
              <p v-else class="mt-1 text-sm text-gray-500">Enter the 6-digit code from your email</p>
            </div>

            <!-- Verification Actions -->
            <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <button
                @click="resendCode"
                :disabled="isResending || resendCooldown > 0"
                class="text-indigo-600 hover:text-indigo-500 font-medium text-sm disabled:text-gray-400 disabled:cursor-not-allowed"
              >
                {{ isResending ? 'Sending...' : resendCooldown > 0 ? `Resend in ${resendCooldown}s` : 'Resend Code' }}
              </button>

              <div class="flex space-x-3">
                <button
                  @click="goBack"
                  class="px-6 py-3 border border-gray-300 rounded-lg font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  ← Back
                </button>
                <button
                  @click="verifyEmail"
                  :disabled="!canVerify || isVerifying"
                  :class="[
                    'px-8 py-3 rounded-lg font-medium transition-all duration-200',
                    'focus:outline-none focus:ring-2 focus:ring-offset-2',
                    canVerify && !isVerifying
                      ? 'bg-indigo-600 hover:bg-indigo-700 text-white focus:ring-indigo-500 shadow-lg hover:shadow-xl'
                      : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  ]"
                >
                  <span v-if="isVerifying" class="flex items-center space-x-2">
                    <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    <span>Verifying...</span>
                  </span>
                  <span v-else>Verify & Complete</span>
                </button>
              </div>
            </div>
          </div>

          <!-- Subscription Form (Original) -->
          <div v-else>
            <!-- Email Input -->
            <div class="mb-8">
              <label for="email" class="block text-sm font-medium text-gray-700 mb-2">
                Email Address *
              </label>
              <div class="relative">
                <input
                  id="email"
                  v-model="email"
                  type="email"
                  :disabled="isSubmitting"
                  :class="[
                    'block w-full px-4 py-3 rounded-lg border-2 transition-colors duration-200',
                    'focus:outline-none focus:ring-0',
                    emailError ? 'border-red-300 focus:border-red-500' :
                    'border-gray-300 focus:border-indigo-500'
                  ]"
                  placeholder="researcher@university.edu"
                  @blur="validateEmail"
                  @input="clearEmailError"
                />
                <div class="absolute inset-y-0 right-0 pr-3 flex items-center">
                  <ExclamationCircleIcon v-if="emailError" class="w-5 h-5 text-red-500" />
                  <AtSymbolIcon v-else class="w-5 h-5 text-gray-400" />
                </div>
              </div>
              <p v-if="emailError" class="mt-1 text-sm text-red-600">{{ emailError }}</p>
              <p v-else class="mt-1 text-sm text-gray-500">
                We'll send you a verification email before activating your subscription
              </p>
            </div>

            <!-- Category Selection -->
            <div class="mb-8">
              <div class="flex items-center justify-between mb-4">
                <label class="block text-sm font-medium text-gray-700">
                  Research Topics *
                </label>
                <span :class="[
                  'text-sm font-medium',
                  selectedTopics.length >= 5 ? 'text-green-600' : 'text-red-600'
                ]">
                  {{ selectedTopics.length }} / 5 minimum selected
                </span>
              </div>

              <!-- Search/Filter -->
              <div class="mb-6">
                <div class="relative">
                  <input
                    v-model="searchTerm"
                    type="text"
                    class="block w-full px-4 py-3 pl-10 pr-4 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    placeholder="Search research areas (e.g., 'machine learning', 'quantum', 'biology')..."
                  />
                  <MagnifyingGlassIcon class="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                </div>
              </div>

              <!-- Selected Topics Summary -->
              <div v-if="selectedTopics.length > 0" class="mb-6 p-4 bg-indigo-50 rounded-lg border border-indigo-200">
                <h4 class="text-sm font-medium text-indigo-900 mb-2">Selected Topics ({{ selectedTopics.length }}):</h4>
                <div class="flex flex-wrap gap-2">
                  <span
                    v-for="topic in selectedTopics"
                    :key="topic"
                    class="inline-flex items-center px-3 py-1 rounded-full text-sm bg-indigo-100 text-indigo-800"
                  >
                    {{ topic }}
                    <button
                      @click="removeSelectedTopic(topic)"
                      class="ml-2 -mr-1 w-4 h-4 rounded-full bg-indigo-200 hover:bg-indigo-300 flex items-center justify-center transition-colors"
                    >
                      <XMarkIcon class="w-3 h-3" />
                    </button>
                  </span>
                </div>
              </div>

              <!-- Category Sections -->
              <div class="space-y-6">
                <div v-for="(categories, domain) in filteredArxivCategories" :key="domain" class="category-section">
                  <h4 class="text-lg font-semibold text-gray-900 mb-4 pb-2 border-b border-gray-200">
                    {{ domain }}
                  </h4>
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div
                      v-for="category in categories"
                      :key="category.id"
                      :class="[
                        'category-card p-4 rounded-lg border-2 cursor-pointer transition-all duration-200',
                        selectedTopics.includes(category.id)
                          ? 'border-indigo-500 bg-indigo-50 shadow-md'
                          : 'border-gray-200 hover:border-gray-300 hover:shadow-sm'
                      ]"
                      @click="toggleTopic(category.id)"
                    >
                      <div class="flex items-start space-x-3">
                        <div class="flex-shrink-0 mt-1">
                          <div :class="[
                            'w-5 h-5 rounded-full border-2 flex items-center justify-center transition-colors',
                            selectedTopics.includes(category.id)
                              ? 'border-indigo-500 bg-indigo-500'
                              : 'border-gray-300'
                          ]">
                            <CheckIcon v-if="selectedTopics.includes(category.id)" class="w-3 h-3 text-white" />
                          </div>
                        </div>
                        <div class="flex-1 min-w-0">
                          <h5 class="text-sm font-semibold text-gray-900 mb-1">
                            {{ category.name }}
                          </h5>
                          <p class="text-xs text-indigo-600 font-medium mb-2">{{ category.id }}</p>
                          <p class="text-sm text-gray-600 line-clamp-3">
                            {{ category.description }}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Submit Button -->
            <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div class="text-sm text-gray-600">
                <p class="flex items-center space-x-2">
                  <ShieldCheckIcon class="w-4 h-4 text-green-500" />
                  <span>Your email will only be used for research summaries</span>
                </p>
              </div>
              <button
                @click="submitSubscription"
                :disabled="!canSubmit || isSubmitting"
                :class="[
                  'px-8 py-3 rounded-lg font-medium transition-all duration-200',
                  'focus:outline-none focus:ring-2 focus:ring-offset-2',
                  canSubmit && !isSubmitting
                    ? 'bg-indigo-600 hover:bg-indigo-700 text-white focus:ring-indigo-500 shadow-lg hover:shadow-xl'
                    : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                ]"
              >
                <span v-if="isSubmitting" class="flex items-center space-x-2">
                  <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span>Sending...</span>
                </span>
                <span v-else>Send Verification Email</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Features Section -->
      <div class="mt-16 grid grid-cols-1 md:grid-cols-3 gap-8">
        <div class="text-center">
          <div class="w-12 h-12 bg-indigo-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <CpuChipIcon class="w-6 h-6 text-indigo-600" />
          </div>
          <h3 class="text-lg font-semibold text-gray-900 mb-2">AI-Powered Summaries</h3>
          <p class="text-gray-600">
            Our advanced AI models read and summarize research papers, highlighting key findings and methodologies in clear Chinese.
          </p>
        </div>
        <div class="text-center">
          <div class="w-12 h-12 bg-indigo-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <DocumentArrowDownIcon class="w-6 h-6 text-indigo-600" />
          </div>
          <h3 class="text-lg font-semibold text-gray-900 mb-2">PDF Attachments</h3>
          <p class="text-gray-600">
            Get the full research papers attached to your email for deeper reading, with smart filename organization.
          </p>
        </div>
        <div class="text-center">
          <div class="w-12 h-12 bg-indigo-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <ClockIcon class="w-6 h-6 text-indigo-600" />
          </div>
          <h3 class="text-lg font-semibold text-gray-900 mb-2">Daily Updates</h3>
          <p class="text-gray-600">
            Receive your personalized research digest every morning at 7:00 AM, keeping you updated with the latest developments.
          </p>
        </div>
      </div>
    </main>

    <!-- Footer -->
    <footer class="bg-white border-t border-gray-200 mt-20">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div class="text-center">
          <h3 class="text-lg font-semibold text-gray-900 mb-2">Cecilia Research Assistant</h3>
          <p class="text-gray-600 mb-4">
            Powered by advanced AI models including DeepSeek-R1-32B. Data sourced from ArXiv.
          </p>
          <div class="flex justify-center space-x-6 text-sm text-gray-500">
            <span>📧 Daily Email Delivery</span>
            <span>🤖 AI Summarization</span>
            <span>📄 PDF Downloads</span>
            <span>🔒 Privacy Protected</span>
          </div>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useToast } from 'vue-toastification'
import {
  CheckIcon,
  ExclamationCircleIcon,
  AtSymbolIcon,
  MagnifyingGlassIcon,
  XMarkIcon,
  ShieldCheckIcon,
  CpuChipIcon,
  DocumentArrowDownIcon,
  ClockIcon
} from '@heroicons/vue/24/outline'
import subscriptionApi from './api/subscriptionApi.js'

// Toast notifications
const toast = useToast()

// Reactive state
const email = ref('')
const emailError = ref('')
const selectedTopics = ref([])
const searchTerm = ref('')
const isSubmitting = ref(false)

// Verification state
const verificationStep = ref(false)
const verificationCode = ref('')
const verificationError = ref('')
const isVerifying = ref(false)
const isResending = ref(false)
const sessionToken = ref('')
const resendCooldown = ref(0)

// ArXiv categories data
const arxivCategories = {
  'Computer Science': [
    { id: 'cs.AI', name: 'Artificial Intelligence', description: 'Covers all areas of AI except Vision, Robotics, Machine Learning, Multiagent Systems, and Computation and Language (Natural Language Processing), which have separate subject areas.' },
    { id: 'cs.AR', name: 'Hardware Architecture', description: 'Covers systems organization and hardware architecture. Roughly includes material in ACM Subject Classes C.0, C.1, and C.5.' },
    { id: 'cs.CC', name: 'Computational Complexity', description: 'Covers models of computation, complexity classes, structural complexity, complexity tradeoffs, upper and lower bounds.' },
    { id: 'cs.CE', name: 'Computational Engineering, Finance, and Science', description: 'Covers applications of computer science to the mathematical modeling of complex systems in the fields of science, engineering, and finance.' },
    { id: 'cs.CG', name: 'Computational Geometry', description: 'Roughly includes material in ACM Subject Classes I.3.5 and F.2.2.' },
    { id: 'cs.CL', name: 'Computation and Language', description: 'Covers natural language processing. Roughly includes material in ACM Subject Class I.2.7.' },
    { id: 'cs.CR', name: 'Cryptography and Security', description: 'Covers all areas of cryptography and security including authentication, public key cryptosystems, proof-carrying code, etc.' },
    { id: 'cs.CV', name: 'Computer Vision and Pattern Recognition', description: 'Covers image processing, computer vision, pattern recognition, and scene understanding.' },
    { id: 'cs.CY', name: 'Computers and Society', description: 'Covers impact of computers on society, computer ethics, information technology and public policy, legal aspects of computing.' },
    { id: 'cs.DB', name: 'Databases', description: 'Covers database management, datamining, and data processing.' },
    { id: 'cs.DC', name: 'Distributed, Parallel, and Cluster Computing', description: 'Covers fault-tolerance, distributed algorithms, stability, parallel computation, and cluster computing.' },
    { id: 'cs.DL', name: 'Digital Libraries', description: 'Covers all aspects of the digital library design and document and text creation.' },
    { id: 'cs.DM', name: 'Discrete Mathematics', description: 'Covers combinatorics, graph theory, applications of probability.' },
    { id: 'cs.DS', name: 'Data Structures and Algorithms', description: 'Covers data structures and analysis of algorithms.' },
    { id: 'cs.ET', name: 'Emerging Technologies', description: 'Covers approaches to information processing based on alternatives to silicon CMOS-based technologies.' },
    { id: 'cs.FL', name: 'Formal Languages and Automata Theory', description: 'Covers automata theory, formal language theory, grammars, and combinatorics on words.' },
    { id: 'cs.GL', name: 'General Literature', description: 'Covers introductory material, survey material, predictions of future trends, biographies.' },
    { id: 'cs.GR', name: 'Graphics', description: 'Covers all aspects of computer graphics.' },
    { id: 'cs.GT', name: 'Computer Science and Game Theory', description: 'Covers all theoretical and applied aspects at the intersection of computer science and game theory.' },
    { id: 'cs.HC', name: 'Human-Computer Interaction', description: 'Covers human factors, user interfaces, and collaborative computing.' },
    { id: 'cs.IR', name: 'Information Retrieval', description: 'Covers indexing, dictionaries, retrieval, content and analysis.' },
    { id: 'cs.IT', name: 'Information Theory', description: 'Covers theoretical and experimental aspects of information theory and coding.' },
    { id: 'cs.LG', name: 'Machine Learning', description: 'Papers on all aspects of machine learning research including robustness, explanation, fairness, and methodology.' },
    { id: 'cs.LO', name: 'Logic in Computer Science', description: 'Covers all aspects of logic in computer science, including finite model theory, logics of programs, modal logic.' },
    { id: 'cs.MA', name: 'Multiagent Systems', description: 'Covers multiagent systems, distributed artificial intelligence, intelligent agents, coordinated interactions.' },
    { id: 'cs.MM', name: 'Multimedia', description: 'Roughly includes material in ACM Subject Class H.5.1.' },
    { id: 'cs.MS', name: 'Mathematical Software', description: 'Roughly includes material in ACM Subject Class G.4.' },
    { id: 'cs.NA', name: 'Numerical Analysis', description: 'Roughly includes material in ACM Subject Class G.1.' },
    { id: 'cs.NE', name: 'Neural and Evolutionary Computing', description: 'Covers neural networks, connectionism, genetic algorithms, artificial life, adaptive behavior.' },
    { id: 'cs.NI', name: 'Networking and Internet Architecture', description: 'Covers all aspects of computer communication networks, including network architecture and design.' },
    { id: 'cs.OH', name: 'Other Computer Science', description: 'This is the classification to use for documents that do not fit anywhere else.' },
    { id: 'cs.OS', name: 'Operating Systems', description: 'Roughly includes material in ACM Subject Classes D.4.1, D.4.2., D.4.3, D.4.4, D.4.5, D.4.7, and D.4.9.' },
    { id: 'cs.PF', name: 'Performance', description: 'Covers performance measurement and evaluation, queueing, and simulation.' },
    { id: 'cs.PL', name: 'Programming Languages', description: 'Covers programming language semantics, language features, programming approaches.' },
    { id: 'cs.RO', name: 'Robotics', description: 'Roughly includes material in ACM Subject Class I.2.9.' },
    { id: 'cs.SC', name: 'Symbolic Computation', description: 'Roughly includes material in ACM Subject Class I.1.' },
    { id: 'cs.SD', name: 'Sound', description: 'Covers all aspects of computing with sound, and sound as an information channel.' },
    { id: 'cs.SE', name: 'Software Engineering', description: 'Covers design tools, software metrics, testing and debugging, programming environments.' },
    { id: 'cs.SI', name: 'Social and Information Networks', description: 'Covers the design, analysis, and modeling of social and information networks.' },
    { id: 'cs.SY', name: 'Systems and Control', description: 'Covers theoretical and experimental research covering all facets of automatic control systems.' }
  ],
  'Mathematics': [
    { id: 'math.AC', name: 'Commutative Algebra', description: 'Commutative rings, modules, ideals, homological algebra, computational aspects, invariant theory.' },
    { id: 'math.AG', name: 'Algebraic Geometry', description: 'Algebraic varieties, stacks, sheaves, schemes, moduli spaces, complex geometry, quantum cohomology.' },
    { id: 'math.AP', name: 'Analysis of PDEs', description: 'Existence and uniqueness, boundary conditions, linear and non-linear operators, stability, soliton theory.' },
    { id: 'math.AT', name: 'Algebraic Topology', description: 'Homotopy theory, homological algebra, algebraic treatments of manifolds.' },
    { id: 'math.CA', name: 'Classical Analysis and ODEs', description: 'Special functions, orthogonal polynomials, harmonic analysis, ODEs, differential relations.' },
    { id: 'math.CO', name: 'Combinatorics', description: 'Discrete mathematics, graph theory, enumeration, combinatorial optimization, Ramsey theory.' },
    { id: 'math.CT', name: 'Category Theory', description: 'Enriched categories, topoi, abelian categories, monoidal categories, homological algebra.' },
    { id: 'math.CV', name: 'Complex Variables', description: 'Holomorphic functions, automorphic group actions and forms, pseudoconvexity, complex geometry.' },
    { id: 'math.DG', name: 'Differential Geometry', description: 'Complex, contact, Riemannian, pseudo-Riemannian and Finsler geometry, relativity, gauge theory.' },
    { id: 'math.DS', name: 'Dynamical Systems', description: 'Dynamics of differential equations and flows, mechanics, classical few-body problems, iterations.' },
    { id: 'math.FA', name: 'Functional Analysis', description: 'Banach spaces, function spaces, real functions, integral transforms, theory of distributions.' },
    { id: 'math.GM', name: 'General Mathematics', description: 'Mathematical material of general interest, topics not covered elsewhere.' },
    { id: 'math.GN', name: 'General Topology', description: 'Continuum theory, point-set topology, spaces with algebraic structure, foundations.' },
    { id: 'math.GR', name: 'Group Theory', description: 'Finite groups, topological groups, representation theory, cohomology, classification and structure.' },
    { id: 'math.GT', name: 'Geometric Topology', description: 'Manifolds, orbifolds, polyhedra, cell complexes, foliations, geometric structures.' },
    { id: 'math.HO', name: 'History and Overview', description: 'Biographies, philosophy of mathematics, mathematics education, recreational mathematics.' },
    { id: 'math.IT', name: 'Information Theory', description: 'Covers theoretical and experimental aspects of information theory and coding.' },
    { id: 'math.KT', name: 'K-Theory and Homology', description: 'Algebraic and topological K-theory, relations with topology, commutative algebra.' },
    { id: 'math.LO', name: 'Logic', description: 'Logic, set theory, point-set topology, formal mathematics.' },
    { id: 'math.MG', name: 'Metric Geometry', description: 'Euclidean, hyperbolic, discrete, convex, coarse geometry, comparisons in Riemannian geometry.' },
    { id: 'math.MP', name: 'Mathematical Physics', description: 'Application of mathematics to problems in physics, develop mathematical methods for such applications.' },
    { id: 'math.NA', name: 'Numerical Analysis', description: 'Numerical algorithms for problems in analysis and algebra, scientific computation.' },
    { id: 'math.NT', name: 'Number Theory', description: 'Prime numbers, diophantine equations, analytic number theory, algebraic number theory.' },
    { id: 'math.OA', name: 'Operator Algebras', description: 'Algebras of operators on Hilbert space, C*-algebras, von Neumann algebras.' },
    { id: 'math.OC', name: 'Optimization and Control', description: 'Operations research, linear programming, control theory, systems theory, optimal control.' },
    { id: 'math.PR', name: 'Probability', description: 'Theory and applications of probability and stochastic processes.' },
    { id: 'math.QA', name: 'Quantum Algebra', description: 'Quantum groups, skein theories, operadic and diagrammatic algebra, quantum field theory.' },
    { id: 'math.RA', name: 'Rings and Algebras', description: 'Non-commutative rings and algebras, non-associative algebras, universal algebra.' },
    { id: 'math.RT', name: 'Representation Theory', description: 'Linear representations of algebras and groups, Lie theory, associative algebras.' },
    { id: 'math.SG', name: 'Symplectic Geometry', description: 'Hamiltonian systems, symplectic flows, classical integrable systems.' },
    { id: 'math.SP', name: 'Spectral Theory', description: 'Schrodinger operators, operators on manifolds, general differential operators.' },
    { id: 'math.ST', name: 'Statistics Theory', description: 'Applied, computational and theoretical statistics: statistical inference, regression, time series.' }
  ],
  'Physics': [
    { id: 'physics.acc-ph', name: 'Accelerator Physics', description: 'Accelerator theory and simulation. Accelerator technology. Accelerator experiments.' },
    { id: 'physics.ao-ph', name: 'Atmospheric and Oceanic Physics', description: 'Atmospheric and oceanic physics and physical chemistry, biogeophysics, and climate science.' },
    { id: 'physics.app-ph', name: 'Applied Physics', description: 'Applications of physics to new technology, including electronic devices, optics, photonics.' },
    { id: 'physics.atom-ph', name: 'Atomic Physics', description: 'Atomic and molecular structure, spectra, collisions, and data. Atoms and molecules in external fields.' },
    { id: 'physics.bio-ph', name: 'Biological Physics', description: 'Molecular biophysics, cellular biophysics, neurological biophysics, membrane biophysics.' },
    { id: 'physics.chem-ph', name: 'Chemical Physics', description: 'Experimental, computational, and theoretical physics of atoms, molecules, and clusters.' },
    { id: 'physics.class-ph', name: 'Classical Physics', description: 'Newtonian and relativistic dynamics; many particle systems; planetary motions.' },
    { id: 'physics.comp-ph', name: 'Computational Physics', description: 'All aspects of computational science applied to physics.' },
    { id: 'physics.data-an', name: 'Data Analysis, Statistics and Probability', description: 'Methods, software and hardware for physics data analysis.' },
    { id: 'physics.ed-ph', name: 'Physics Education', description: 'Research studies, laboratory experiences, assessment or classroom practices for improving physics teaching.' },
    { id: 'physics.flu-dyn', name: 'Fluid Dynamics', description: 'Turbulence, instabilities, incompressible/compressible flows, reacting flows.' },
    { id: 'physics.gen-ph', name: 'General Physics', description: 'General physics topics.' },
    { id: 'physics.geo-ph', name: 'Geophysics', description: 'Atmospheric physics, biogeosciences, computational geophysics, geographic location.' },
    { id: 'physics.hist-ph', name: 'History and Philosophy of Physics', description: 'History and philosophy of all branches of physics, astrophysics, and cosmology.' },
    { id: 'physics.ins-det', name: 'Instrumentation and Detectors', description: 'Instrumentation and detectors for research in natural science.' },
    { id: 'physics.med-ph', name: 'Medical Physics', description: 'Radiation therapy, radiation dosimetry, biomedical imaging modelling.' },
    { id: 'physics.optics', name: 'Optics', description: 'Adaptive optics, astronomical optics, atmospheric optics, biomedical optics.' },
    { id: 'physics.plasm-ph', name: 'Plasma Physics', description: 'Fundamental plasma physics, magnetically confined plasmas, high energy density plasmas.' },
    { id: 'physics.pop-ph', name: 'Popular Physics', description: 'Popular physics topics.' },
    { id: 'physics.soc-ph', name: 'Physics and Society', description: 'Structure, dynamics and collective behavior of societies and groups.' },
    { id: 'physics.space-ph', name: 'Space Physics', description: 'Space plasma physics, heliophysics, space weather, planetary magnetospheres.' }
  ],
  'Statistics': [
    { id: 'stat.AP', name: 'Applications', description: 'Biology, Education, Epidemiology, Engineering, Environmental Sciences, Medical, Physical Sciences.' },
    { id: 'stat.CO', name: 'Computation', description: 'Algorithms, Simulation, Visualization.' },
    { id: 'stat.ME', name: 'Methodology', description: 'Design, Surveys, Model Selection, Multiple Testing, Multivariate Methods, Signal and Image Processing.' },
    { id: 'stat.ML', name: 'Machine Learning', description: 'Covers machine learning papers with a statistical or theoretical grounding.' },
    { id: 'stat.OT', name: 'Other Statistics', description: 'Work in statistics that does not fit into the other stat classifications.' },
    { id: 'stat.TH', name: 'Statistics Theory', description: 'Asymptotics, Bayesian Inference, Decision Theory, Estimation, Foundations, Inference.' }
  ],
  'Electrical Engineering': [
    { id: 'eess.AS', name: 'Audio and Speech Processing', description: 'Theory and methods for processing signals representing audio, speech, and language.' },
    { id: 'eess.IV', name: 'Image and Video Processing', description: 'Theory, algorithms, and architectures for the formation, capture, processing of images and video.' },
    { id: 'eess.SP', name: 'Signal Processing', description: 'Theory, algorithms, performance analysis and applications of signal and data analysis.' },
    { id: 'eess.SY', name: 'Systems and Control', description: 'Theoretical and experimental research covering all facets of automatic control systems.' }
  ],
  'Quantitative Biology': [
    { id: 'q-bio.BM', name: 'Biomolecules', description: 'DNA, RNA, proteins, lipids; molecular structures and folding kinetics; molecular interactions.' },
    { id: 'q-bio.CB', name: 'Cell Behavior', description: 'Cell-cell signaling and interaction; morphogenesis and development; apoptosis.' },
    { id: 'q-bio.GN', name: 'Genomics', description: 'DNA sequencing and assembly; gene and motif finding; RNA editing and alternative splicing.' },
    { id: 'q-bio.MN', name: 'Molecular Networks', description: 'Gene regulation, signal transduction, proteomics, metabolomics, gene and enzymatic networks.' },
    { id: 'q-bio.NC', name: 'Neurons and Cognition', description: 'Synapse, cortex, neuronal dynamics, neural network, sensorimotor control, behavior.' },
    { id: 'q-bio.OT', name: 'Other Quantitative Biology', description: 'Work in quantitative biology that does not fit into the other classifications.' },
    { id: 'q-bio.PE', name: 'Populations and Evolution', description: 'Population dynamics, spatio-temporal and epidemiological models, dynamic speciation.' },
    { id: 'q-bio.QM', name: 'Quantitative Methods', description: 'All experimental, numerical, statistical and mathematical contributions of value to biology.' },
    { id: 'q-bio.SC', name: 'Subcellular Processes', description: 'Assembly and control of subcellular structures; molecular motors, transport.' },
    { id: 'q-bio.TO', name: 'Tissues and Organs', description: 'Blood flow in vessels, biomechanics of bones, electrical waves, endocrine system.' }
  ]
}

// Computed properties
const filteredArxivCategories = computed(() => {
  if (!searchTerm.value.trim()) {
    return arxivCategories
  }

  const search = searchTerm.value.toLowerCase()
  const filtered = {}

  Object.keys(arxivCategories).forEach(domain => {
    const matchingCategories = arxivCategories[domain].filter(category =>
      category.name.toLowerCase().includes(search) ||
      category.description.toLowerCase().includes(search) ||
      category.id.toLowerCase().includes(search)
    )

    if (matchingCategories.length > 0) {
      filtered[domain] = matchingCategories
    }
  })

  return filtered
})

const canSubmit = computed(() => {
  return email.value &&
         selectedTopics.value.length >= 5 &&
         !emailError.value &&
         !isSubmitting.value
})

const canVerify = computed(() => {
  return verificationCode.value.length === 6 && !isVerifying.value
})

// Methods
const validateEmail = () => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!email.value) {
    emailError.value = 'Email is required'
  } else if (!emailRegex.test(email.value)) {
    emailError.value = 'Please enter a valid email address'
  } else {
    emailError.value = ''
  }
}

const clearEmailError = () => {
  if (emailError.value) {
    emailError.value = ''
  }
}

const toggleTopic = (topicId) => {
  const index = selectedTopics.value.indexOf(topicId)
  if (index > -1) {
    selectedTopics.value.splice(index, 1)
  } else {
    selectedTopics.value.push(topicId)
  }
}

const removeSelectedTopic = (topicId) => {
  const index = selectedTopics.value.indexOf(topicId)
  if (index > -1) {
    selectedTopics.value.splice(index, 1)
  }
}

const handleVerificationInput = (event) => {
  // Only allow digits
  const value = event.target.value.replace(/\D/g, '').slice(0, 6)
  verificationCode.value = value
  verificationError.value = ''
}

const handleKeyPress = (event) => {
  // Only allow digits
  if (!/\d/.test(event.key) && !['Backspace', 'Delete', 'ArrowLeft', 'ArrowRight', 'Tab'].includes(event.key)) {
    event.preventDefault()
  }
}

const submitSubscription = async () => {
  if (!canSubmit.value) return

  isSubmitting.value = true
  verificationError.value = ''

  try {
    const result = await subscriptionApi.createSubscription(email.value, selectedTopics.value)

    if (result.success) {
      sessionToken.value = result.sessionToken
      verificationStep.value = true
      toast.success('Verification email sent! Please check your inbox.')
    } else {
      throw new Error(result.error || 'Failed to create subscription')
    }

  } catch (error) {
    console.error('Subscription error:', error)
    toast.error(error.message || 'Failed to create subscription. Please try again.')
  } finally {
    isSubmitting.value = false
  }
}

const verifyEmail = async () => {
  if (!canVerify.value) return

  isVerifying.value = true
  verificationError.value = ''

  try {
    const result = await subscriptionApi.verifyEmail(sessionToken.value, verificationCode.value)

    if (result.success) {
      toast.success('🎉 Subscription activated! You will receive daily research summaries at 7:00 AM.')

      // Show success state
      setTimeout(() => {
        // Reset form
        email.value = ''
        selectedTopics.value = []
        verificationStep.value = false
        verificationCode.value = ''
        sessionToken.value = ''
      }, 3000)
    } else {
      throw new Error(result.error || 'Verification failed')
    }

  } catch (error) {
    console.error('Verification error:', error)
    verificationError.value = error.message
    toast.error(error.message)
  } finally {
    isVerifying.value = false
  }
}

const resendCode = async () => {
  if (!sessionToken.value || isResending.value || resendCooldown.value > 0) return

  isResending.value = true

  try {
    const result = await subscriptionApi.resendVerificationCode(sessionToken.value)

    if (result.success) {
      toast.success('New verification code sent!')
      verificationCode.value = ''
      verificationError.value = ''

      // Start cooldown
      resendCooldown.value = 60
      const cooldownTimer = setInterval(() => {
        resendCooldown.value -= 1
        if (resendCooldown.value <= 0) {
          clearInterval(cooldownTimer)
        }
      }, 1000)
    } else {
      throw new Error(result.error || 'Failed to resend code')
    }

  } catch (error) {
    console.error('Resend error:', error)
    toast.error(error.message)
  } finally {
    isResending.value = false
  }
}

const goBack = () => {
  verificationStep.value = false
  verificationCode.value = ''
  verificationError.value = ''
  sessionToken.value = ''
}

// Lifecycle
onMounted(() => {
  console.log('Cecilia subscription app loaded!')
})
</script>

<style scoped>
.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.category-card {
  transition: all 0.2s ease-in-out;
}

.category-card:hover {
  transform: translateY(-1px);
}

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
