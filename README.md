# CrateDigger -- A Behavioral Mapping Platform for Intentional Audio Consumption

CrateDigger is an ongoing project stemming from a web development course I completed in Spring 2026. The web application is
intended to build off of Discogs and its music catalogging capabilties by providing:

- collection browsing with sorts and filters
- listening sessions with pre/post mood logging
- 'mood tags' to assign to albums as you listen to them
- mood-based recommender system to recommend albums to a user (more info to be added...)
- history and listening stats page to view all past listening sessions

## Prerequisites

To get the most out of CrateDigger, you will need to have:

1. Discogs account -- this can be set up for free if you do not already have one
2. Access to the Discogs API -- requested through your Discogs account for free
3. Access to the Gemini API -- requested through Google AI Studio for free*

In case it is not clear at this point, you can set up and use the various features of this project completely for free.

*With the Gemini API, you have up to 20 requests per day that are free (based on the free tier benefits for Gemini-2.5-flash-lite),
and after that you would need to either wait for the limit to reset or set up a payment through your Google AI Studio account. 
Reaching the request rate limit would only prevent you from getting the LLM recommendations; all other features should be available.

## Setting Up

You can choose to download all of the files from this repository individually, however I recommend simply cloning the 
repository to get started:

`git clone https://github.com/byork-bork/cratedigger.git`

You will also need to edit the .env file to include your API keys for both Discogs and Gemini.

`DISCOGS_TOKEN=<put_your_api_token_here>`

`GEMINI_API_KEY=<put_your_api_token_here>`

There is a requirements.txt file included in this repository to install all of the dependencies I had for working on this project, 
however the main Python package you need to absolutely have is Django (which is in the requirements.txt).

`pip install -r requirements.txt`

Once you have the above steps completed, you can access the root folder of the repo through your terminal and run the Django server:

`python manage.py runserver`

You will be provided a link to a localhost page. Accessing that link should show the webpage, and then you can proceed to using CrateDigger.
