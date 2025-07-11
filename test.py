import asyncio
import json
import logging
from pathlib import Path
from apps.email_service.email_service import EmailService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_email_service():
    """Test email service functionality"""
    
    # Initialize email service
    email_service = EmailService()
    
    # Load email targets from essay_summarizer directory
    email_targets_file = Path("data/essay_summarizer/email_targets.json")
    
    if not email_targets_file.exists():
        logger.error("email_targets.json not found. Creating empty file...")
        # Create directories if they don't exist
        email_targets_file.parent.mkdir(parents=True, exist_ok=True)
        # Create empty email targets file
        with open(email_targets_file, 'w', encoding='utf-8') as f:
            json.dump([], f, indent=2)
        print("Created empty email_targets.json file. Please add email addresses to test.")
        return
    
    # Load email targets
    try:
        with open(email_targets_file, 'r', encoding='utf-8') as f:
            email_targets = json.load(f)
    except Exception as e:
        logger.error(f"Error loading email targets: {e}")
        return
    
    if not email_targets:
        print("No email targets found in email_targets.json")
        print("Please add email addresses to the file in this format:")
        print('["email1@example.com", "email2@example.com"]')
        return
    
    print(f"Found {len(email_targets)} email target(s): {email_targets}")
    
    # Create test paper data
    test_papers = [
        {
            'title': 'Test Paper 1: Advanced Machine Learning Techniques',
            'authors': ['张三', '李四', 'John Smith'],
            'summary': '这是一篇关于先进机器学习技术的测试论文。论文提出了一种新的深度学习方法，能够显著提高模型的准确性和效率。主要贡献包括：1) 提出了创新的网络架构；2) 开发了高效的训练算法；3) 在多个基准数据集上取得了最先进的结果。',
            'pdf_url': 'https://arxiv.org/pdf/2101.00001v1',
            'categories': ['cs.LG', 'cs.AI', 'stat.ML']
        },
        {
            'title': 'Test Paper 2: Quantum Computing Applications',
            'authors': ['王五', 'Alice Johnson'],
            'summary': '本研究探讨了量子计算在实际应用中的前景。论文详细分析了量子算法的优势，并提出了几个具有实用价值的量子应用场景。研究结果表明，量子计算在密码学、优化问题和机器学习等领域具有巨大潜力。',
            'pdf_url': 'https://arxiv.org/pdf/2101.00002v1',
            'categories': ['quant-ph', 'cs.CR']
        }
    ]
    
    # Test statistics
    test_stats = {
        'papers_count': len(test_papers),
        'new_papers': 1,
        'cached_papers': 1
    }
    
    print("\n=== Testing Email Service ===")
    print("Sending test email with sample papers...")
    
    try:
        # Send test email
        result = await email_service.send_paper_summary_email(
            to_emails=email_targets,
            category='cs',
            topic='machine learning',
            papers=test_papers,
            stats=test_stats
        )
        
        if result['success']:
            print("✅ Email sent successfully!")
            print(f"Recipients: {result['recipients']}")
            print(f"Subject: {result['subject']}")
            print("\nPlease check the recipient email inbox(es) to verify email delivery.")
        else:
            print("❌ Email sending failed!")
            print(f"Error: {result['error']}")
            
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        logger.exception("Full error traceback:")

def test_email_config():
    """Test email configuration validation"""
    print("\n=== Testing Email Configuration ===")
    
    from bot.auths import (
        EMAIL_SMTP_HOST, EMAIL_SMTP_PORT, EMAIL_SMTP_SECURE,
        EMAIL_SMTP_USER, EMAIL_SMTP_PASS, EMAIL_SMTP_NAME
    )
    
    print(f"SMTP Host: {EMAIL_SMTP_HOST}")
    print(f"SMTP Port: {EMAIL_SMTP_PORT}")
    print(f"SMTP Secure: {EMAIL_SMTP_SECURE}")
    print(f"SMTP User: {EMAIL_SMTP_USER}")
    print(f"SMTP Name: {EMAIL_SMTP_NAME}")
    print(f"SMTP Pass: {'*' * len(EMAIL_SMTP_PASS) if EMAIL_SMTP_PASS else 'Not set'}")
    
    # Validate configuration
    required_fields = [EMAIL_SMTP_HOST, EMAIL_SMTP_USER, EMAIL_SMTP_PASS]
    if all(required_fields):
        print("✅ Email configuration appears complete")
    else:
        print("❌ Email configuration incomplete!")
        if not EMAIL_SMTP_HOST:
            print("  - SMTP Host not set")
        if not EMAIL_SMTP_USER:
            print("  - SMTP User not set")
        if not EMAIL_SMTP_PASS:
            print("  - SMTP Password not set")
        print("Please check your bot/auths.py file")

async def test_simple_email():
    """Send a simple test email without papers"""
    print("\n=== Testing Simple Email ===")
    
    email_service = EmailService()
    
    # Load email targets
    email_targets_file = Path("data/essay_summarizer/email_targets.json")
    
    if not email_targets_file.exists():
        print("email_targets.json not found. Cannot test.")
        return
    
    try:
        with open(email_targets_file, 'r', encoding='utf-8') as f:
            email_targets = json.load(f)
    except Exception as e:
        print(f"Error loading email targets: {e}")
        return
    
    if not email_targets:
        print("No email targets found.")
        return
    
    # Send simple test email with no papers
    test_stats = {
        'papers_count': 0,
        'new_papers': 0,
        'cached_papers': 0
    }
    
    try:
        result = await email_service.send_paper_summary_email(
            to_emails=email_targets,
            category='test',
            topic='email functionality',
            papers=[],  # Empty papers list
            stats=test_stats
        )
        
        if result['success']:
            print("✅ Simple test email sent successfully!")
            print(f"Subject: {result['subject']}")
        else:
            print("❌ Simple email test failed!")
            print(f"Error: {result['error']}")
            
    except Exception as e:
        print(f"❌ Simple email test failed with exception: {e}")

async def main():
    """Main test function"""
    print("=== Cecilia Email Service Test ===")
    
    # Test configuration first
    test_email_config()
    
    # Test simple email
    await test_simple_email()
    
    # Test full email with papers
    await test_email_service()
    
    print("\n=== Test Complete ===")
    print("If emails were sent successfully, please check the recipient inbox(es).")

if __name__ == "__main__":
    asyncio.run(main())
