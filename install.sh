python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
echo "Cecilia is ready to use! Run 'deploy.sh' to deploy the bot on port 8010."
echo "Make sure to fill 'bot/auths-sample.py' with your discord bot credentials and rename it to 'auths.py'."
