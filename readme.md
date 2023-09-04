# Marketplace Connect Flow Example
## Introduction
The objective of this code sample is to help partners to make their Symphony bot compliant with the requirements of the **Marketplace Connect flow**.

It is based on the Java BDK. If you are not familiar with the Symphony Java BDK, please have a look here: https://github.com/finos/symphony-bdk-java

## Disclaimer
This code sample is only an example. It is not meant to be directly used in a production environment. 

## Requirements for the Connect flow
The requirements of the Connect flow are to provide a good user experience to Symphony users who will connect to your bot from the Marketplace.
This means:
- Automatically accept incoming connection requests.
- And automatically send an introduction message when a new user connects to the bot.
  - This message could contain a thank you message & a user mention to drag attention. It would also inform about the next steps required to get access to the service.
  - Optionally, it gives access to a subset of the service or offers a limited time access. This part is not included in the code sample. In that case it also contains info on how to get support as well as how to interact with the bot.

## Get Started
```
git clone
```
Add RSA private key in /rsa/privatekey.pem

Edit config.yaml in /resources/config.yaml
- Update host with your pod url
- Update username with your bot username
- Set path to rsa key (default /rsa/privatekey.pem)

Edit source code in connections_listener.py with your own parameters for the support email address, sales email address and company name. See below:
```
supportEmail = "vinay@symphony.com"
salesEmail = "partners@symphony.com"
company = "Awesome Company, LLC"
```

## First run only:
1. Create virtual environment:
    - `python3 -m venv env`
2. Install dependencies:
    - `pip3 install -r requirements.txt`

## Subsequent runs:
- Activate virtual environment
    - macOS/Linux: `source env/bin/activate`
    - Windows: `env\Scripts\activate.bat`

## Run project
- `python3 -m src`
