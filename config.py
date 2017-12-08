"""Configuration settings for running the Python auth samples locally.

In a production deployment, this information should be saved in a database or
other secure storage mechanism.
"""

CLIENT_ID = 'ENTER_YOUR_CLIENT_ID'
CLIENT_SECRET = 'ENTER_YOUR_SECRET'
REDIRECT_URI = 'http://localhost:5000/login/authorized'

AUTHORITY_URL = 'https://login.microsoftonline.com/common'
AUTH_ENDPOINT = '/oauth2/v2.0/authorize'
TOKEN_ENDPOINT = '/oauth2/v2.0/token'

RESOURCE = 'https://graph.microsoft.com/'
API_VERSION = 'beta' # need beta API to get profile photo for Microsoft Accounts
SCOPES = ['User.Read', 'Mail.Send', 'Files.ReadWrite']

# This code can be removed after configuring CLIENT_ID and CLIENT_SECRET above.
if 'ENTER_YOUR' in CLIENT_ID or 'ENTER_YOUR' in CLIENT_SECRET:
    print('ERROR: config.py does not contain valid CLIENT_ID and CLIENT_SECRET')
    import sys
    sys.exit(1)
