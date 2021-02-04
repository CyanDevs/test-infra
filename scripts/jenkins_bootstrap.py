#!/usr/bin/env python3
"""jenkins-trigger.py
Usage:
    jenkins-trigger.py --job <jobname> --jenkins-user <username> --jenkins-password <password> [--url <url>] [--retries <int>] [--encoding <type>] [--parameters <data>] [--debug]
    jenkins-trigger.py -h
Examples:
    jenkins-trigger.py  --job deploy_my_app -e text -u https://jenkins.example.com:8080 -p param1=1,param2=develop
Options:
  -j, --job <jobname>               Job Name.
  --jenkins-user <username>         Jenkins username.
  --jenkins-password <password>     Jenkins Password.
  -u, --url <url>                   Jenkins URL [default: http://localhost:8080]
  -r, --retries <int>               Retries for requests [default: 12]
  -e, --encoding <type>             Encoding type supports text or html [default: text]
  -p, --parameters <data>           Comma separated job parameters i.e. a=1,b=2
  -d, --debug                       Print debug info
  -h, --help                        Show this screen and exit.
"""

from docopt import docopt
from time import sleep
from urllib3.util.retry import Retry
from re import search

import requests
import logging
import atexit

def binary_backoff(retries):
    """
    Increment by a multiplier based off of number of retries made

    Returns: <int> which resembles number of seconds used to sleep
    """
    # Try (#)              | 1 | 2 | 3 | 4 | 5  | 6  | 7  | 8   | 9   | 10  | 11   | 12   | 13   ...
    # Backoff factor 2 (s) | 1 | 2 | 4 | 8 | 16 | 32 | 64 | 128 | 256 | 512 | 1024 | 2056 | 4096 ...
    backoff_factor = 2
    return backoff_factor * ( 2 ** (retries - 1))


class Trigger:

    def __init__(self, arguments):

        # Configure retries for http(s) requests
        adapter = requests.adapters.HTTPAdapter(
            max_retries=Retry(
                # Retry total defaults to 12
                total=ARGUMENTS['--retries'][0],
                status_forcelist=[429, 500, 502, 503, 504],
                method_whitelist=["HEAD", "GET", "OPTIONS"],
                # Binary backoff where timeout = {backoff factor} * (2 ** ({current retries} - 1))
                backoff_factor=2
            )
        )

        # Create request session and mount adapters
        self.http = requests.Session()
        self.http.mount("https://", adapter)
        self.http.mount("http://", adapter)

        # Handle Parameters with docopt
        self.arguments = arguments
        self.debug = arguments['--debug']
        self.job = arguments['--job'][0]
        self.user = arguments['--jenkins-user']
        self.password = arguments['--jenkins-password']
        self.url = arguments['--url'][0]
        self.encoding = arguments['--encoding'][0]
        self.retries = int(arguments['--retries'][0])
        self.crumb = self.fetch_crumb()
        self.token = self.fetch_token()

        if self.encoding.lower() in ["html", "text"]:
            self.encoding = self.encoding.title()
        else:
            raise ValueError(f"{self.encoding} is not a valid encoding only support 'text', 'html'")

        if arguments['--parameters']:
            try:
                self.parameters = dict(u.split("=") for u in arguments['--parameters'][0].split(","))
            except ValueError as err:
                raise Exception("Your parameters should be in key=value format separated by , for multi value i.e. x=1,b=2") from err
        else:
            self.parameters = {}

    def return_json(self, url, auth=None, data=None):
        """ Safely return json from a request """

        response = self.http.get(
            url = url,
            auth = auth,
            data = data
        )
        if self.debug:
            print(
                f'GET Request {url}'
                f'HTTP {str(response.status_code)}\n'
                f'{response.text}\n'
                f'Received Cookies {str(response.cookies.get_dict())}'
            )
        # Catch 4xx and 5xx errors although 429, 500, 502, 503, 504 are already retried
        response.raise_for_status()

        if response.json():
            return response.json()
        return None

    def fetch_crumb(self):
        """Obtains a user crumb from Jenkins API"""

        url = f'{self.url}/crumbIssuer/api/json'
        auth = (self.user, self.password)
        print(f'Fetching: {url}')

        crumb_json = self.return_json(url, auth)
        if crumb_json.get('crumb'):
            return crumb_json.get('crumb')

    def fetch_token(self):
        """ Generates an API token for use during this script """

        print('Fetching API Token')
        token_response = self.http.post(
            url = f'{self.url}/me/descriptorByName/jenkins.security.ApiTokenProperty/generateNewToken',
            auth = (self.user, self.password),
            headers = {"Jenkins-Crumb": self.crumb}
        )
        if token_response.status_code == 200 and token_response.json().get('data', None):
            atexit.register(self.handler_revoke_token)
            print('Received token successfully')
            return {
                'uuid': token_response.json().get('data').get('tokenUuid'),
                'value': token_response.json().get('data').get('tokenValue')
            }
        else:
            raise ValueError(
                f"API Token generation failed!\n"
                f"Response status: {token_response.status_code}\n"
                f'Content: {token_response.content}'
            )

    def trigger_build(self):
        """Trigger a build via Jenkins API"""

        def fail_trigger(reason):
            """ Fail the build trigger with a reason """

            raise ValueError(
                f"Build trigger failed!\n"
                f"Response status: {build_response.status_code}\n"
                f'Reason: {reason}\n'
                f'Content: {build_response.content}'
            )

        # Do a build request
        if self.parameters:
            build_url = f'{self.url}/job/{self.job}/buildWithParameters'
        else:
            build_url = f'{self.url}/job/{self.job}/build'
        print(f'Triggering a build via POST @ {build_url}')
        build_response = self.http.post(
            url = build_url,
            data = self.parameters,
            auth = (self.user, self.token['value']),
            headers = {"Jenkins-Crumb": self.crumb}
        )

        # Check response to build request
        if build_response.status_code == 201:

            # Get queue url to get queue updates
            queue_url = f"{build_response.headers.get('location')}api/json"
            if queue_url:
                # Edge case where queue url in response is not fully qualified
                if queue_url.startswith('/'):
                    queue_url = f"{self.url}{queue_url}"
                print(f'Build is queued @ {queue_url}')

                # Set a handler to cancel the Job if this script exits
                atexit.register(self.handler_abort_job, queue_url)

                return queue_url

        # Account for the some of the many ways a build trigger can fail
        # Note that some connection errors will be automatically retried as part of the HTTPAdapter
        elif build_response.status_code == 400:
            fail_trigger("Bad request. Likely build trigger is missing parameters to build with")
        elif build_response.status_code == 401:
            fail_trigger("Invalid user/password provided")
        elif build_response.status_code == 403:
            fail_trigger("Missing permissions to trigger a build")
        elif build_response.status_code == 404:
            fail_trigger("This job does not exist. Please check your job name and url")
        elif build_response.status_code == 409:
            fail_trigger("This job seems to be disabled")
        else:
            fail_trigger("Failed to trigger build. Please see response content for causes.")

    def waiting_for_job_to_start(self, queue_url):
        """Query if a Jenkins job starts building"""

        # Increase number of retries by 5 to ensure enough time is spent waiting in queue
        max_retries = self.retries + 5
        for retry in range(max_retries):

            # Check if job url is available yet
            print(f'Checking job status at {queue_url} (#{retry+1}/{max_retries})')
            queue_json = self.return_json(queue_url)

            if queue_json.get('executable') and queue_json.get("executable").get("url"):
                job_url = queue_json.get("executable").get("url")
                print(f'Job is executing: {job_url}')
                return job_url

            elif queue_json.get('why'):
                print(f"Job is in queue because: {queue_json.get('why')}")

            elif queue_json.get('cancelled'):
                print(f"Job is cancelled. Exiting...")
                atexit.unregister(self.handler_abort_job)
                exit(1)

            elif self.debug:
                print(queue_json)

            # Do not sleep for last loop
            if retry + 1 < max_retries:
                # Binary backoff before next attempt, but have a ceiling of 256 seconds
                # to account for Jenkins queue items being garbage collected every 5 min
                next_sleep = min(binary_backoff(retry), 256)
                print(f'Sleeping for {next_sleep}s...')
                sleep(next_sleep)

        raise TimeoutError("Exceeded timeout waiting for queue item to start")

    def check_job_status(self, job_url):
        """
        Check to see if a job is still running

        Returns one of the following: 'running', 'failure', 'success', 'aborted'
        """

        status_json = self.return_json(f'{job_url}api/json')
        if status_json.get("building"):
            if self.debug:
                print("Trigger.check_job_status(): Job is still running...")
            return 'running'
        else:
            if self.debug:
                print(f"Trigger.check_job_status(): Job returned {status_json.get('result').lower()}")
            return status_json.get("result").lower()

    def check_log_completed(self, content):
        """Check to see if a job log is done with a job completion line"""

        if search('Finished: (SUCCESS|FAILED|FAILURE|ABORTED)', content):
            if self.debug:
                print(f"Trigger.check_log_completed(): Found Jenkins job completion line!")
            return True
        return False

    def complete_job(self, result):
        """Perform an action based off a job result"""

        if result in ['failure', 'failed', 'aborted']:
            atexit.unregister(self.handler_abort_job)
            raise SystemExit(f"Job {result}")
        elif result == 'success':
            print(f"Stream closed with a successful job")
            atexit.unregister(self.handler_abort_job)
            raise SystemExit(0)

    def console_output(self, job_url):
        """Get Jenkins job console output until job completes"""

        start_at = 0
        no_progress_counter = 0
        stream_open = True
        console_url = f'{job_url}logText/progressive{self.encoding}'

        # Register handler to exit job once it starts
        atexit.unregister(self.handler_abort_job)
        atexit.register(self.handler_abort_job, job_url)

        print(f'Getting Console output: {console_url}')
        while stream_open:
            console_response = self.http.post(
                url = console_url,
                data = {'start': start_at},
                auth = (self.user, self.token['value'])
            )
            content_length = int(console_response.headers.get("Content-Length", 0))

            # Case on handling log output
            if content_length > 0:
                # Print to screen console
                print(console_response.text)

                # Close stream if logs are completed
                stream_open = not self.check_log_completed(console_response.text)

                if stream_open:
                    # Prepare for next run
                    no_progress_counter = 0
                    start_at = int(console_response.headers.get("X-Text-Size", 0))
                    sleep(10)
                else:
                    self.complete_job(self.check_job_status(job_url))

            # Case on handling no output or content-length returned nothing
            else:
                if self.debug:
                    print(
                        f"Trigger.console_output():\n"
                        f"content_length: {content_length}\n"
                        f"no_progress_counter: {no_progress_counter}"
                    )
                # Case when there has been no output for an extended period without logs printing a completion line
                #   This could technically just keep counting up without ending.
                #   We don't want to end it so not as to set a limit on how long Jenkins build jobs can take.
                #   But it is unreasonable to go a day without any log output and Jenkins still considers it running
                #   so that may change, but it is more so an issue with Jenkins than this script
                if no_progress_counter > 7:
                    status = self.check_job_status(job_url)
                    if status != 'running':
                        self.complete_job(status)
                        stream_open = False

                sleep(binary_backoff(no_progress_counter))
                no_progress_counter += 1

    def handler_abort_job(self, url):
        """ Abort a running Jenkins job if the script exits before the job completes """

        # Note: job may not actually be aborted during Jenkins sleep timers
        # See a somewhat similar issue: https://issues.jenkins.io/browse/JENKINS-59494

        for retry in range(self.retries):

            # Adapter for stop url
            if '/job/' in url:
                stop_url = f"{url}stop"
            elif '/queue/' in url:
                queue_item_search = search(r"\/queue\/item/(\d+)\/", url)
                stop_url = f"{self.url}/queue/cancelItem?id={queue_item_search.group(1)}"

            print(f"Exiting script and aborting Jenkins job: {stop_url} (Try #{retry+1}/{self.retries})")

            stop_response = self.http.post(
                url = stop_url,
                auth = (self.user, self.token['value']),
                headers = {"Jenkins-Crumb": self.crumb}
            )

            sleep(3)
            # Check if job stopped
            if '/job/' in url:
                status = self.check_job_status(url)
                if status != 'running':
                    self.complete_job(status)
                else:
                    sleep(binary_backoff(retry))
            elif '/queue/' in url:
                # Queue item stop response will return a 500 if it is no longer in queue
                if stop_response.status_code == 500:
                    print("Job has left queue.")
                    # Check status of Job
                    job_url = self.waiting_for_job_to_start(url)
                    # If queue item started between initial exit and abort request, abort Job instead
                    if job_url:
                        print("Job is already building. Killing build instead.")
                        self.handler_abort_job(job_url)

    def handler_revoke_token(self):
        """ Revokes the API token generated in the same session """

        print(f'Revoking API token')
        token_response = self.http.post(
            url = f'{self.url}/me/descriptorByName/jenkins.security.ApiTokenProperty/revoke',
            data = {"tokenUuid": self.token['uuid']},
            auth = (self.user, self.token['value']),
            headers = {"Jenkins-Crumb": self.crumb}
        )
        if token_response.status_code != 200:
            raise ValueError(
                f"API Token was not revoked!\n"
                f"Response status: {token_response.status_code}\n"
                f'Content: {token_response.content}'
            )

    def main(self):

        # Enable logging
        if self.debug:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.WARN)

        queue_url = self.trigger_build()
        job_url = self.waiting_for_job_to_start(queue_url)
        self.console_output(job_url)


if __name__ == '__main__':
    ARGUMENTS = docopt(__doc__)
    MY_TRIGGER = Trigger(ARGUMENTS)
    MY_TRIGGER.main()
