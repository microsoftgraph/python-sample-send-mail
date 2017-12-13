"""send-email sample for Microsoft Graph"""
# Copyright (c) Microsoft. All rights reserved. Licensed under the MIT license.
# See LICENSE in the project root for license information.
import base64
import mimetypes
import os
import pprint
import uuid

import flask
from flask_oauthlib.client import OAuth

import config

APP = flask.Flask(__name__, template_folder='static/templates')
APP.debug = True
APP.secret_key = 'development'
OAUTH = OAuth(APP)
MSGRAPH = OAUTH.remote_app(
    'microsoft',
    consumer_key=config.CLIENT_ID,
    consumer_secret=config.CLIENT_SECRET,
    request_token_params={'scope': config.SCOPES},
    base_url=config.RESOURCE + config.API_VERSION + '/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url=config.AUTHORITY_URL + config.TOKEN_ENDPOINT,
    authorize_url=config.AUTHORITY_URL + config.AUTH_ENDPOINT)

@APP.route('/')
def homepage():
    """Render the home page."""
    return flask.render_template('homepage.html')

@APP.route('/login')
def login():
    """Prompt user to authenticate."""
    flask.session['state'] = str(uuid.uuid4())
    return MSGRAPH.authorize(callback=config.REDIRECT_URI, state=flask.session['state'])

@APP.route('/login/authorized')
def authorized():
    """Handler for the application's Redirect Uri."""
    if str(flask.session['state']) != str(flask.request.args['state']):
        raise Exception('state returned to redirect URL does not match!')
    response = MSGRAPH.authorized_response()
    flask.session['access_token'] = response['access_token']
    return flask.redirect('/mailform')

@APP.route('/mailform')
def mailform():
    """Sample form for sending email via Microsoft Graph."""

    # read user profile data
    user_profile = MSGRAPH.get('me', headers=request_headers()).data
    user_name = user_profile['displayName']

    # get profile photo
    photo_data, _, profile_pic = profile_photo(client=MSGRAPH, save_as='me')
    # save photo data as config.photo for use in mailform.html/mailsent.html
    if profile_pic:
        config.photo = base64.b64encode(photo_data).decode()
    else:
        profile_pic = 'static/images/no-profile-photo.png'
        with open(profile_pic, 'rb') as fhandle:
            config.photo = base64.b64encode(fhandle.read()).decode()

    # upload profile photo to OneDrive
    upload_response = upload_file(client=MSGRAPH, filename=profile_pic)
    if str(upload_response.status).startswith('2'):
        # create a sharing link for the uploaded photo
        link_url = sharing_link(client=MSGRAPH, item_id=upload_response.data['id'])
    else:
        link_url = ''

    body = flask.render_template('email.html', name=user_name, link_url=link_url)
    return flask.render_template('mailform.html',
                                 name=user_name,
                                 email=user_profile['userPrincipalName'],
                                 profile_pic=profile_pic,
                                 photo_data=config.photo,
                                 link_url=link_url,
                                 body=body)

@APP.route('/send_mail')
def send_mail():
    """Handler for send_mail route."""
    profile_pic = flask.request.args['profile_pic']

    response = sendmail(client=MSGRAPH,
                        subject=flask.request.args['subject'],
                        recipients=flask.request.args['email'].split(';'),
                        body=flask.request.args['body'],
                        attachments=[flask.request.args['profile_pic']])

    # show results in the mailsent form
    response_json = pprint.pformat(response.data)
    response_json = None if response_json == "b''" else response_json
    return flask.render_template('mailsent.html',
                                 sender=flask.request.args['sender'],
                                 email=flask.request.args['email'],
                                 profile_pic=profile_pic,
                                 photo_data=config.photo,
                                 subject=flask.request.args['subject'],
                                 body_length=len(flask.request.args['body']),
                                 response_status=response.status,
                                 response_json=response_json)

@MSGRAPH.tokengetter
def get_token():
    """Called by flask_oauthlib.client to retrieve current access token."""
    return (flask.session.get('access_token'), '')

def request_headers(headers=None):
    """Return dictionary of default HTTP headers for Graph API calls.
    Optional argument is other headers to merge/override defaults."""
    default_headers = {'SdkVersion': 'sample-python-flask',
                       'x-client-SKU': 'sample-python-flask',
                       'client-request-id': str(uuid.uuid4()),
                       'return-client-request-id': 'true'}
    if headers:
        default_headers.update(headers)
    return default_headers

def profile_photo(*, client=None, user_id='me', save_as=None):
    """Get profile photo.

    client  = user-authenticated flask-oauthlib client instance
    user_id = Graph id value for the user, or 'me' (default) for current user
    save_as = optional filename to save the photo locally. Should not include an
              extension - the extension is determined by photo's content type.

    Returns a tuple of the photo (raw data), content type, saved filename.
    """
    endpoint = 'me/photo/$value' if user_id == 'me' else f'users/{user_id}/$value'
    photo_response = client.get(endpoint)
    if str(photo_response.status).startswith('2'):
        # HTTP status code is 2XX, so photo was returned successfully
        photo = photo_response.raw_data
        metadata_response = client.get(endpoint[:-7]) # remove /$value to get metadata
        content_type = metadata_response.data.get('@odata.mediaContentType', '')
    else:
        photo = ''
        content_type = ''

    if photo and save_as:
        extension = content_type.split('/')[1]
        if extension == 'pjpeg':
            extension = 'jpeg' # to correct known issue with content type
        filename = save_as + '.' + extension
        with open(filename, 'wb') as fhandle:
            fhandle.write(photo)
    else:
        filename = ''

    return (photo, content_type, filename)

def sendmail(*, client, subject=None, recipients=None, body='',
             content_type='HTML', attachments=None):
    """Helper to send email from current user.

    client       = user-authenticated flask-oauthlib client instance
    subject      = email subject (required)
    recipients   = list of recipient email addresses (required)
    body         = body of the message
    content_type = content type (default is 'HTML')
    attachments  = list of file attachments (local filenames)

    Returns the response from the POST to the sendmail API.
    """

    # Verify that required arguments have been passed.
    if not all([client, subject, recipients]):
        raise ValueError('sendmail(): required arguments missing')

    # Create recipient list in required format.
    recipient_list = [{'EmailAddress': {'Address': address}}
                      for address in recipients]

    # Create list of attachments in required format.
    attached_files = []
    if attachments:
        for filename in attachments:
            b64_content = base64.b64encode(open(filename, 'rb').read())
            mime_type = mimetypes.guess_type(filename)[0]
            mime_type = mime_type if mime_type else ''
            attached_files.append( \
                {'@odata.type': '#microsoft.graph.fileAttachment',
                 'ContentBytes': b64_content.decode('utf-8'),
                 'ContentType': mime_type,
                 'Name': filename})

    # Create email message in required format.
    email_msg = {'Message': {'Subject': subject,
                             'Body': {'ContentType': content_type, 'Content': body},
                             'ToRecipients': recipient_list,
                             'Attachments': attached_files},
                 'SaveToSentItems': 'true'}

    # Do a POST to Graph's sendMail API and return the response.
    return client.post('me/microsoft.graph.sendMail',
                       headers=request_headers(),
                       data=email_msg,
                       format='json')

def sharing_link(*, client, item_id, link_type='view'):
    """Get a sharing link for an item in OneDrive.

    client    = user-authenticated flask-oauthlib client instance
    item_id   = the id of the DriveItem (the target of the link)
    link_type = 'view' (default), 'edit', or 'embed' (OneDrive Personal only)

    Returns the sharing link.
    """
    endpoint = f'me/drive/items/{item_id}/createLink'
    response = client.post(endpoint,
                           headers=request_headers(),
                           data={'type': link_type},
                           format='json')

    if str(response.status).startswith('2'):
        # status 201 = link created, status 200 = existing link returned
        return response.data['link']['webUrl']

def upload_file(*, client, filename, folder=None):
    """Upload a file to OneDrive for Business.

    client  = user-authenticated flask-oauthlib client instance
    filename = local filename; may include a path
    folder = destination subfolder/path in OneDrive for Business
             None (default) = root folder

    File is uploaded and the response object is returned.
    If file already exists, it is overwritten.
    If folder does not exist, it is created.

    API documentation:
    https://developer.microsoft.com/en-us/graph/docs/api-reference/v1.0/api/driveitem_put_content
    """
    fname_only = os.path.basename(filename)

    # create the Graph endpoint to be used
    if folder:
        # create endpoint for upload to a subfolder
        endpoint = f'me/drive/root:/{folder}/{fname_only}:/content'
    else:
        # create endpoint for upload to drive root folder
        endpoint = f'me/drive/root/children/{fname_only}/content'

    content_type, _ = mimetypes.guess_type(fname_only)
    with open(filename, 'rb') as fhandle:
        file_content = fhandle.read()

    return client.put(endpoint,
                      headers=request_headers({'content-type': content_type}),
                      data=file_content,
                      content_type=content_type)

if __name__ == '__main__':
    APP.run()
