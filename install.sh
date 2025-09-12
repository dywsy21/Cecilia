python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp bot/config-sample.py bot/config.py
cp bot/auths-sample.py bot/auth.py

echo "Cecilia is ready to use! Run 'deploy.sh' to deploy the bot on port 8010."
echo "Make sure to fill 'bot/auths.py' with your discord bot credentials and also fill in your configs in 'bot/config.py'.
