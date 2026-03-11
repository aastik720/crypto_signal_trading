PROMPT FOR PHASE 19:

PROJECT: CryptoSignal Bot (7-Brain System)  
PHASE: 19 - AWS EC2 Deployment

SETUP:
- AMI: Ubuntu 22.04 LTS
- Instance: t2.micro (free tier)
- Storage: 8GB EBS

STEPS:
1. Launch EC2, configure security group (SSH only)
2. SSH into instance
3. Install Python 3.10+, pip, git
4. Upload project / git clone
5. Create virtual environment
6. Install requirements
7. Create .env file with all secrets
8. Test run: python main.py
9. Create systemd service for auto-start:

   /etc/systemd/system/cryptobot.service:
   [Unit]
   Description=CryptoSignal Bot
   After=network.target
   [Service]
   Type=simple
   User=ubuntu
   WorkingDirectory=/home/ubuntu/crypto_signal_bot
   Environment=PATH=/home/ubuntu/crypto_signal_bot/venv/bin
   ExecStart=/home/ubuntu/crypto_signal_bot/venv/bin/python main.py
   Restart=always
   RestartSec=10
   [Install]
   WantedBy=multi-user.target

10. Enable and start service
11. Set up log rotation
12. Set up health check cron (every 5 minutes)
13. Set up daily database backup
14. Set billing alerts in AWS

MEMORY: ~50MB for 10 pairs × 100 candles × 7 brains
t2.micro (1GB RAM) is more than enough.