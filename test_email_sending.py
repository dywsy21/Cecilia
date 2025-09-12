import asyncio
import json
import logging
import asyncio
import logging
import json
from pathlib import Path
from apps.email_service.email_service import EmailService
from apps.llm_handler.llm_handler import LLMHandler

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_test_pdf_files():
    """Create dummy PDF files for testing email attachments"""
    processed_dir = Path("data/essay_summarizer/processed")
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    # Create minimal valid PDF content for testing
    test_pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT
/F1 12 Tf
72 720 Td
(Test PDF Content) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000207 00000 n 
trailer
<< /Size 5 /Root 1 0 R >>
startxref
295
%%EOF"""
    
    # Create test PDF files matching the test paper URLs
    test_files = [
        "2101.00001v1.pdf",
        "2101.00002v1.pdf",
        "2024.12345v1.pdf"
    ]
    
    created_files = []
    for filename in test_files:
        file_path = processed_dir / filename
        with open(file_path, 'wb') as f:
            f.write(test_pdf_content)
        created_files.append(file_path)
        logger.info(f"Created test PDF: {file_path}")
    
    return created_files

def test_email_config():
    """Test email configuration validation"""
    print("\n" + "="*50)
    print("=== Testing Email Configuration ===")
    print("="*50)
    
    try:
        from bot.auths import (
            EMAIL_SMTP_HOST, EMAIL_SMTP_PORT, EMAIL_SMTP_SECURE,
            EMAIL_SMTP_USER, EMAIL_SMTP_PASS, EMAIL_SMTP_NAME
        )
        
        print(f"📧 SMTP Host: {EMAIL_SMTP_HOST}")
        print(f"🔌 SMTP Port: {EMAIL_SMTP_PORT}")
        print(f"🔐 SMTP Secure: {EMAIL_SMTP_SECURE}")
        print(f"👤 SMTP User: {EMAIL_SMTP_USER}")
        print(f"📛 SMTP Name: {EMAIL_SMTP_NAME}")
        print(f"🔑 SMTP Pass: {'*' * len(EMAIL_SMTP_PASS) if EMAIL_SMTP_PASS else 'Not set'}")
        
        # Validate configuration
        required_fields = [EMAIL_SMTP_HOST, EMAIL_SMTP_USER, EMAIL_SMTP_PASS]
        if all(required_fields):
            print("✅ Email configuration appears complete")
            return True
        else:
            print("❌ Email configuration incomplete!")
            if not EMAIL_SMTP_HOST:
                print("  - SMTP Host not set")
            if not EMAIL_SMTP_USER:
                print("  - SMTP User not set")
            if not EMAIL_SMTP_PASS:
                print("  - SMTP Password not set")
            print("Please check your bot/auths.py file")
            return False
            
    except ImportError as e:
        print(f"❌ Cannot import email configuration: {e}")
        print("Please ensure bot/auths.py exists and contains email settings")
        return False

def load_email_targets():
    """Load and validate email targets with new format"""
    email_targets_file = Path("data/essay_summarizer/email_targets.json")
    
    if not email_targets_file.exists():
        print("📁 email_targets.json not found. Creating empty file...")
        email_targets_file.parent.mkdir(parents=True, exist_ok=True)
        with open(email_targets_file, 'w', encoding='utf-8') as f:
            json.dump({}, f, indent=2)
        print("✅ Created empty email_targets.json file")
        print("📝 Please add email addresses in this format:")
        print('   {')
        print('     "email1@example.com": ["cs.ai", "cs.cv"],')
        print('     "email2@example.com": ["cs.lg", "eess.sp"]')
        print('   }')
        return {}
    
    try:
        with open(email_targets_file, 'r', encoding='utf-8') as f:
            email_targets = json.load(f)
        
        # Handle old format migration
        if isinstance(email_targets, list):
            print("📁 Migrating from old format to new format...")
            new_format = {email: [] for email in email_targets}
            with open(email_targets_file, 'w', encoding='utf-8') as f:
                json.dump(new_format, f, indent=2)
            print("✅ Migration completed. Please update email_targets.json with paper types.")
            return new_format
        
        if not email_targets:
            print("📭 No email targets found in email_targets.json")
            print("📝 Please add email addresses in this format:")
            print('   {')
            print('     "email1@example.com": ["cs.ai", "cs.cv"],')
            print('     "email2@example.com": ["cs.lg", "eess.sp"]')
            print('   }')
            return {}
        
        print(f"📧 Found {len(email_targets)} email target(s):")
        for email, paper_types in email_targets.items():
            print(f"   {email}: {paper_types}")
        return email_targets
        
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in email_targets.json: {e}")
        return {}
    except Exception as e:
        print(f"❌ Error loading email targets: {e}")
        return {}

async def test_simple_email():
    """Test sending a simple email without papers or attachments"""
    print("\n" + "="*50)
    print("=== Testing Simple Email (No Papers) ===")
    print("="*50)
    
    email_service = EmailService()
    email_targets = load_email_targets()
    
    if not email_targets:
        print("⏭️  Skipping simple email test - no email targets")
        return False
    
    test_stats = {
        'papers_count': 0,
        'new_papers': 0,
        'cached_papers': 0
    }
    
    try:
        # Use first email address for testing
        test_email = list(email_targets.keys())[0]
        print(f"📤 Sending simple test email to {test_email}...")
        
        result = await email_service.send_paper_summary_email(
            to_emails=[test_email],
            category='test',
            topic='email functionality',
            papers=[],  # Empty papers list
            stats=test_stats
        )
        
        if result['success']:
            print("✅ Simple test email sent successfully!")
            print(f"📬 Subject: {result['subject']}")
            print(f"📎 Attachments: {result.get('attachments', 0)} (should be 0)")
            return True
        else:
            print("❌ Simple email test failed!")
            print(f"💥 Error: {result['error']}")
            return False
            
    except Exception as e:
        print(f"❌ Simple email test failed with exception: {e}")
        logger.exception("Full error traceback:")
        return False

async def test_email_with_papers():
    """Test sending email with papers and PDF attachments"""
    print("\n" + "="*50)
    print("=== Testing Email with Papers & Attachments ===")
    print("="*50)
    
    email_service = EmailService()
    email_targets = load_email_targets()
    
    if not email_targets:
        print("⏭️  Skipping papers email test - no email targets")
        return False
    
    # Create test PDF files
    print("📄 Creating test PDF files...")
    created_files = await create_test_pdf_files()
    print(f"✅ Created {len(created_files)} test PDF files")
    
    # Create test paper data with realistic content
    test_papers = [
        {
            'title': 'Advanced Deep Learning Architectures for Computer Vision: A Comprehensive Survey and Novel Transformer-Based Approach',
            'authors': ['张明华', '李晓雨', 'Dr. Sarah Johnson', 'Prof. Michael Chen', '王建国'],
            'summary': '''本研究提出了一种创新的深度学习架构，结合了Transformer机制和卷积神经网络的优势。
            
主要贡献包括：
1. 设计了多尺度注意力机制，显著提升了图像特征提取能力
2. 提出了自适应权重融合策略，有效整合不同层次的特征信息  
3. 在ImageNet和CIFAR-100数据集上取得了最先进的性能表现
4. 模型参数量减少了30%，推理速度提升了25%

实验结果表明，该方法在图像分类、目标检测和语义分割等多个计算机视觉任务中都展现出卓越的性能。特别是在小样本学习场景下，相比现有方法准确率提升了8.5%。这一突破为计算机视觉领域的实际应用提供了新的可能性。''',
            'pdf_url': 'https://arxiv.org/pdf/2101.00001v1',
            'categories': ['cs.CV', 'cs.LG', 'cs.AI', 'stat.ML']
        },
        {
            'title': 'Quantum Machine Learning: Bridging Quantum Computing and Artificial Intelligence for Next-Generation Applications',
            'authors': ['Dr. Alice Quantum', '刘志强', 'Prof. Bob Einstein', '陈小芳'],
            'summary': '''本论文探索了量子机器学习的前沿进展，重点研究量子计算在人工智能中的革命性应用。

核心创新：
1. 开发了量子增强的神经网络训练算法，训练速度提升指数级
2. 设计了量子特征映射技术，能够处理经典计算机难以解决的高维问题
3. 提出了量子-经典混合优化框架，充分利用两种计算范式的优势
4. 在药物分子设计和金融风险预测中验证了方法的有效性

研究结果显示，量子机器学习在解决NP-hard问题方面具有显著优势，为密码学、优化理论和复杂系统建模开辟了新的研究方向。该工作为量子计算的实用化进程贡献了重要力量。''',
            'pdf_url': 'https://arxiv.org/pdf/2101.00002v1',
            'categories': ['quant-ph', 'cs.LG', 'cs.CR', 'physics.comp-ph']
        },
        {
            'title': 'Sustainable AI: Green Computing Strategies for Large-Scale Neural Network Training',
            'authors': ['Prof. Green Smith', '赵环保', 'Dr. Emma Climate', '孙可持续'],
            'summary': '''面对人工智能训练过程中日益严重的能耗问题，本研究提出了一套绿色AI训练策略。

主要贡献：
1. 开发了能耗感知的神经网络架构搜索算法，平衡精度和效率
2. 设计了分布式训练的动态负载均衡机制，优化数据中心能源利用
3. 提出了模型压缩与知识蒸馏的联合优化方法
4. 建立了AI碳足迹评估标准和可持续发展指标体系

实验证明，采用我们的方法可以在保持模型性能的同时，将训练能耗降低高达60%。这一成果对推动AI产业的可持续发展具有重要意义，为构建环境友好的人工智能生态系统提供了技术支撑。''',
            'pdf_url': 'https://arxiv.org/pdf/2024.12345v1',
            'categories': ['cs.LG', 'cs.DC', 'cs.CY', 'eess.SY']
        }
    ]
    
    test_stats = {
        'papers_count': len(test_papers),
        'new_papers': 2,
        'cached_papers': 1
    }
    
    try:
        # Use first email address for testing
        test_email = list(email_targets.keys())[0]
        print(f"📤 Sending email with {len(test_papers)} papers to {test_email}...")
        print("📎 Expected attachments:")
        for i, paper in enumerate(test_papers, 1):
            title = paper['title'][:60] + "..." if len(paper['title']) > 60 else paper['title']
            print(f"   {i}. {title}.pdf")
        
        result = await email_service.send_paper_summary_email(
            to_emails=[test_email],
            category='cs',
            topic='artificial intelligence',
            papers=test_papers,
            stats=test_stats
        )
        
        if result['success']:
            print("✅ Email with papers sent successfully!")
            print(f"📬 Subject: {result['subject']}")
            print(f"👥 Recipients: {result['recipients']}")
            print(f"📎 PDF Attachments: {result.get('attachments', 0)}")
            print(f"📧 Expected attachment names:")
            for i, paper in enumerate(test_papers, 1):
                sanitized_title = email_service._sanitize_filename(paper['title'])
                print(f"   {i}. {sanitized_title}.pdf")
            return True
        else:
            print("❌ Email with papers failed!")
            print(f"💥 Error: {result['error']}")
            return False
            
    except Exception as e:
        print(f"❌ Papers email test failed with exception: {e}")
        logger.exception("Full error traceback:")
        return False

async def test_multiple_paper_types():
    """Test sending emails for multiple paper types (new feature)"""
    print("\n" + "="*50)
    print("=== Testing Multiple Paper Types Email ===")
    print("="*50)
    
    email_service = EmailService()
    email_targets = load_email_targets()
    
    if not email_targets:
        print("⏭️  Skipping multiple paper types test - no email targets")
        return False
    
    # Create test PDF files
    print("📄 Creating test PDF files...")
    created_files = await create_test_pdf_files()
    print(f"✅ Created {len(created_files)} test PDF files")
    
    # Test different paper types that a user might subscribe to
    paper_type_tests = [
        {
            'category': 'cs',
            'topic': 'ai',
            'papers': [
                {
                    'title': 'Artificial Intelligence Advances in Natural Language Processing',
                    'authors': ['Dr. AI Smith', '李人工智能'],
                    'summary': '本研究探讨了自然语言处理领域的最新AI进展，提出了新的预训练模型架构，在多项基准测试中取得了突破性成果。',
                    'pdf_url': 'https://arxiv.org/pdf/2101.00001v1',
                    'categories': ['cs.AI', 'cs.CL']
                }
            ]
        },
        {
            'category': 'cs', 
            'topic': 'cv',
            'papers': [
                {
                    'title': 'Computer Vision Breakthroughs in Object Detection',
                    'authors': ['Prof. Vision Expert', '张计算机视觉'],
                    'summary': '本论文介绍了目标检测领域的重大突破，新算法在准确率和速度方面都有显著提升，为实时应用奠定了基础。',
                    'pdf_url': 'https://arxiv.org/pdf/2101.00002v1',
                    'categories': ['cs.CV', 'cs.LG']
                }
            ]
        },
        {
            'category': 'eess',
            'topic': 'sp', 
            'papers': [
                {
                    'title': 'Signal Processing Applications in Modern Communication Systems',
                    'authors': ['Dr. Signal Proc', '王信号处理'],
                    'summary': '本研究提出了现代通信系统中信号处理的新方法，显著改善了信号质量和传输效率，为5G/6G技术发展提供支撑。',
                    'pdf_url': 'https://arxiv.org/pdf/2024.12345v1',
                    'categories': ['eess.SP', 'cs.IT']
                }
            ]
        }
    ]
    
    # Test first email address that has paper type subscriptions
    test_email = None
    test_paper_types = []
    
    for email, paper_types in email_targets.items():
        if paper_types:  # Find an email with actual paper type subscriptions
            test_email = email
            test_paper_types = paper_types
            break
    
    if not test_email:
        print("⏭️  No email addresses with paper type subscriptions found")
        print("📝 Please add paper types to an email address in email_targets.json")
        return False
    
    print(f"🎯 Testing with email: {test_email}")
    print(f"📚 Subscribed paper types: {test_paper_types}")
    
    success_count = 0
    total_tests = len(paper_type_tests)
    
    for i, test_case in enumerate(paper_type_tests, 1):
        try:
            category = test_case['category']
            topic = test_case['topic']
            papers = test_case['papers']
            paper_type = f"{category}.{topic}"
            
            print(f"\n📧 Test {i}/{total_tests}: Sending {paper_type} papers...")
            
            # Check if this paper type is in the user's subscriptions
            if paper_type not in test_paper_types:
                print(f"⏭️  Skipping {paper_type} - not in user's subscriptions")
                continue
            
            stats = {
                'papers_count': len(papers),
                'new_papers': len(papers),
                'cached_papers': 0
            }
            
            result = await email_service.send_paper_summary_email(
                to_emails=[test_email],
                category=category,
                topic=topic,
                papers=papers,
                stats=stats
            )
            
            if result['success']:
                print(f"✅ {paper_type} email sent successfully!")
                print(f"📬 Subject: {result['subject']}")
                print(f"📎 Attachments: {result.get('attachments', 0)}")
                success_count += 1
            else:
                print(f"❌ {paper_type} email failed!")
                print(f"💥 Error: {result['error']}")
            
            # Add delay between emails to avoid rate limiting
            await asyncio.sleep(2)
            
        except Exception as e:
            print(f"❌ Error testing paper type {test_case['category']}.{test_case['topic']}: {e}")
            continue
    
    print(f"\n📊 Multiple paper types test results: {success_count}/{total_tests} successful")
    return success_count > 0

async def test_email_configuration_connectivity():
    """Test SMTP connectivity without sending actual emails"""
    print("\n" + "="*50)
    print("=== Testing SMTP Connectivity ===")
    print("="*50)
    
    try:
        from bot.auths import (
            EMAIL_SMTP_HOST, EMAIL_SMTP_PORT, EMAIL_SMTP_SECURE,
            EMAIL_SMTP_USER, EMAIL_SMTP_PASS
        )
        
        import smtplib
        import ssl
        
        print(f"🔗 Attempting connection to {EMAIL_SMTP_HOST}:{EMAIL_SMTP_PORT}...")
        
        if EMAIL_SMTP_SECURE:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT, context=context) as server:
                print("✅ SSL connection established")
                server.login(EMAIL_SMTP_USER, EMAIL_SMTP_PASS)
                print("✅ Authentication successful")
        else:
            with smtplib.SMTP(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT) as server:
                print("✅ SMTP connection established")
                context = ssl.create_default_context()
                server.starttls(context=context)
                print("✅ TLS upgrade successful")
                server.login(EMAIL_SMTP_USER, EMAIL_SMTP_PASS)
                print("✅ Authentication successful")
        
        print("🎉 SMTP connectivity test passed!")
        return True
        
    except Exception as e:
        print(f"❌ SMTP connectivity test failed: {e}")
        return False

def create_sample_email_targets():
    """Create a sample email_targets.json file with examples"""
    print("\n" + "="*50)
    print("=== Creating Sample Email Targets File ===")
    print("="*50)
    
    email_targets_file = Path("data/essay_summarizer/email_targets.json")
    email_targets_file.parent.mkdir(parents=True, exist_ok=True)
    
    sample_data = {
        "researcher1@university.edu": [
            "cs.ai",
            "cs.cv", 
            "cs.lg"
        ],
        "engineer@company.com": [
            "cs.ar",
            "eess.sp",
            "eess.sy"
        ],
        "student@school.edu": [
            "cs.ai",
            "stat.ml",
            "math.oc"
        ]
    }
    
    try:
        with open(email_targets_file, 'w', encoding='utf-8') as f:
            json.dump(sample_data, f, indent=2, ensure_ascii=False)
        
        print("✅ Sample email_targets.json created successfully!")
        print("📝 Sample configuration:")
        for email, paper_types in sample_data.items():
            print(f"   {email}: {paper_types}")
        
        print("\n💡 To use for testing:")
        print("1. Replace sample email addresses with real ones")
        print("2. Modify paper types according to your interests")
        print("3. Run the email tests again")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to create sample file: {e}")
        return False

async def cleanup_test_files():
    """Clean up test PDF files"""
    try:
        processed_dir = Path("data/essay_summarizer/processed")
        test_files = ["2101.00001v1.pdf", "2101.00002v1.pdf", "2024.12345v1.pdf"]
        
        cleaned = 0
        for filename in test_files:
            file_path = processed_dir / filename
            if file_path.exists():
                file_path.unlink()
                cleaned += 1
        
        if cleaned > 0:
            print(f"🧹 Cleaned up {cleaned} test PDF files")
            
    except Exception as e:
        print(f"⚠️  Warning: Could not clean up test files: {e}")

async def test_llm_configuration():
    """Test LLM configuration and connectivity"""
    print("\n" + "="*50)
    print("=== Testing LLM Configuration ===")
    print("="*50)
    
    try:
        llm_handler = LLMHandler()
        provider_info = llm_handler.get_provider_info()
        
        print(f"🤖 LLM Provider: {provider_info['provider']}")
        print(f"📱 Model: {provider_info['model']}")
        print(f"🌐 Base URL: {provider_info['base_url']}")
        
        if provider_info['provider'] == 'OPENAI':
            if provider_info['has_api_key']:
                print("✅ API Key configured")
            else:
                print("❌ API Key not configured")
                return False
        
        print("🔄 Testing LLM service connectivity...")
        is_available = await llm_handler.check_service()
        
        if is_available:
            print(f"✅ {provider_info['provider']} service is accessible")
            
            # Test a simple summarization
            print("📝 Testing paper summarization...")
            test_content = """
            This is a test paper about artificial intelligence and machine learning.
            It discusses various approaches to neural networks and their applications.
            The paper introduces a novel architecture that improves performance by 20%.
            """
            test_summary = await llm_handler.summarize_paper(test_content, "Test AI Paper")
            
            if test_summary:
                print(f"✅ LLM summarization test successful")
                print(f"📄 Summary length: {len(test_summary)} characters")
                return True
            else:
                print("❌ LLM summarization test failed")
                return False
        else:
            print(f"❌ {provider_info['provider']} service is not accessible")
            return False
            
    except Exception as e:
        print(f"❌ LLM configuration test failed: {e}")
        return False

async def main():
    """Main test function with comprehensive email testing including new features"""
    print("🤖 Cecilia Email Service Test Suite - Advanced Edition")
    print("Testing email functionality with LLM integration")
    
    # Test basic email configuration
    test_email_config()
    
    # Test LLM configuration
    llm_ok = await test_llm_configuration()
    if not llm_ok:
        print("⚠️  LLM tests failed, but email tests can still continue")
    
    # Create sample email targets if needed
    create_sample_email_targets()
    
    # Test basic email functionality
    await test_simple_email()
    
    # Test email with papers and attachments
    await test_email_with_papers()
    
    # Test multiple paper types
    await test_multiple_paper_types()
    
    # Test SMTP connectivity
    await test_email_configuration_connectivity()
    
    # Cleanup test files
    await cleanup_test_files()
    
    print("\n" + "="*50)
    print("=== Email Test Suite Complete ===")
    print("="*50)
    print("✅ All email tests completed!")
    print("📧 Check your email inbox for test messages")
    print("🔧 Adjust configuration in bot/auths.py and data/essay_summarizer/email_targets.json as needed")
    print("="*60)
    
    test_results = {
        'config': False,
        'connectivity': False,
        'simple_email': False,
        'papers_email': False,
        'multiple_paper_types': False,
        'llm_configuration': False
    }
    
    try:
        # Test 1: Configuration validation
        test_results['config'] = test_email_config()
        
        if not test_results['config']:
            print("\n❌ Email configuration is incomplete. Please fix configuration first.")
            return
        
        # Test 2: SMTP connectivity  
        test_results['connectivity'] = await test_email_configuration_connectivity()
        
        if not test_results['connectivity']:
            print("\n❌ SMTP connectivity failed. Please check network and credentials.")
            return
        
        # Check if email targets exist and offer to create sample
        email_targets = load_email_targets()
        if not email_targets:
            print("\n📝 No email targets found. Would you like to create a sample configuration?")
            create_sample_email_targets()
            print("\n⏭️  Please update the sample file with real email addresses and run the test again.")
            return
        
        # Test 3: Simple email
        test_results['simple_email'] = await test_simple_email()
        
        # Test 4: Email with papers and attachments
        test_results['papers_email'] = await test_email_with_papers()
        
        # Test 5: Multiple paper types (NEW FEATURE)
        test_results['multiple_paper_types'] = await test_multiple_paper_types()
        
        # Test 6: LLM configuration and connectivity
        test_results['llm_configuration'] = await test_llm_configuration()
        
    finally:
        # Cleanup
        await cleanup_test_files()
    
    # Summary
    print("\n" + "="*60)
    print("=== Test Results Summary ===")
    print("="*60)
    
    total_tests = len(test_results)
    passed_tests = sum(test_results.values())
    
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        display_name = test_name.replace('_', ' ').title()
        print(f"{display_name:.<35} {status}")
    
    print(f"\nOverall: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! Email system with new features is working correctly.")
        print("📧 You should now check the recipient email inbox(es) to verify delivery.")
        print("📚 The new per-user paper type subscription system is ready for use!")
    elif test_results['config'] and test_results['connectivity']:
        print("⚠️  Email configuration works, but some email tests failed.")
        print("🔍 Check email targets configuration and try again.")
    else:
        print("❌ Email system needs configuration. Please check bot/auths.py")
    
    print("\n📝 Next steps:")
    print("1. Verify email delivery in recipient inboxes")
    print("2. Check PDF attachments are properly named and readable")
    print("3. Update email_targets.json with real email addresses and paper types")
    print("4. Test with actual research paper subscriptions")
    print("5. Verify the new per-user paper type subscription workflow")
    
    print("\n🔧 New Features Tested:")
    print("• Per-user paper type subscriptions")
    print("• Multiple emails per user for different topics")
    print("• Enhanced email target format: {email: [paper_types]}")
    print("• PDF attachments with numbered, readable filenames")
    print("• Rich HTML email templates with paper summaries")

if __name__ == "__main__":
    asyncio.run(main())
