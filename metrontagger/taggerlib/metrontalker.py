"""Python class to communicate with Metron.cloud"""
import json
import platform
import ssl
import time
from datetime import datetime
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from darkseid.genericmetadata import GenericMetadata
from darkseid.issuestring import IssueString
from darkseid.utils import list_to_string
from ratelimit import limits, sleep_and_retry

from .. import VERSION

ONE_MINUTE = 60


class MetronTalker:
    """Python class to communicate with Metron's REST"""

    def __init__(self, auth):
        self.api_base_url = "https://metron.cloud/api"
        self.auth_str = f"Basic {auth.decode('utf-8')}"
        self.user_agent = (
            f"Metron-Tagger/{VERSION} ({platform.system()}; {platform.release()})"
        )
        self.ssl = ssl.SSLContext(ssl.PROTOCOL_TLS)

    @classmethod
    def parse_date_string(cls, date_str):
        """
        Classmethod that takes a date from Metron's REST API and splits it into it's components
        """
        day = None
        month = None
        year = None
        if date_str is not None:
            parts = date_str.split("-")
            year = parts[0]
            if len(parts) > 1:
                month = parts[1]
                if len(parts) > 2:
                    day = parts[2]
        return day, month, year

    @sleep_and_retry
    @limits(calls=20, period=ONE_MINUTE)
    def fetch_response(self, url):
        """Function to retrieve a response from Metron's REST API"""
        request = Request(url)
        request.add_header("Authorization", self.auth_str)
        request.add_header("User-Agent", self.user_agent)

        try:
            content = urlopen(request, context=self.ssl)
        except HTTPError as http_error:
            # TODO: Look into handling throttling better, but for now let's use this.
            if http_error.code == 429:
                print("Exceeded api rate limit. Sleeping for 30 seconds...")
                time.sleep(30)
                return self.fetch_response(url)
            raise

        resp = json.loads(content.read().decode("utf-8"))

        return resp

    def fetch_issue_data_by_issue_id(self, issue_id):
        """Method to get an issue's metadata by supplying the issue id"""
        url = self.api_base_url + f"/issue/{issue_id}/?format=json"
        resp = self.fetch_response(url)
        meta_data = self.map_metron_data_to_metadata(resp)
        meta_data.isEmpty = False

        return meta_data

    def search_for_issue(self, query_dict):
        """
        Method to search for an issue based on a dictionary of
        words, volume number, or year.
        """
        url = (
            self.api_base_url
            + f"/issue/?series_name={query_dict['series']}&number={query_dict['number']}"
        )
        if query_dict["volume"]:
            url += f"&series_volume={query_dict['volume']}"
        if query_dict["year"]:
            url += f"&cover_year={query_dict['year']}"
        url += "&format=json"
        resp = self.fetch_response(url)

        return resp

    def map_metron_data_to_metadata(self, issue_results):
        """
        Method to map the issue results from Metron's REST API
        to metadata
        """
        metadata = GenericMetadata()

        metadata.series = issue_results["series"]["name"]
        metadata.volume = issue_results["volume"]

        num_s = IssueString(issue_results["number"]).as_string()

        metadata.issue = num_s

        titles = issue_results["name"]
        if titles is not None:
            title_list = []
            for title in titles:
                title_list.append(title)
            metadata.title = list_to_string(title_list)

        metadata.publisher = issue_results["publisher"]["name"]
        metadata.day, metadata.month, metadata.year = self.parse_date_string(
            issue_results["cover_date"]
        )

        metadata.comments = issue_results["desc"]

        now_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        metadata.notes = (
            f"Tagged with MetronTagger-{VERSION} using info from Metron on {now_date}. "
            + f"[issue_id:{issue_results['id']}]"
        )

        person_credits = issue_results["credits"]
        for person in person_credits:
            if "role" in person:
                roles = person["role"]
                for role in roles:
                    metadata.add_credit(person["creator"], role["name"], False)

        character_credits = issue_results["characters"]
        character_list = []
        for character in character_credits:
            character_list.append(character["name"])
        metadata.characters = list_to_string(character_list)

        team_credits = issue_results["teams"]
        team_list = []
        for team in team_credits:
            team_list.append(team["name"])
        metadata.teams = list_to_string(team_list)

        story_arc_credits = issue_results["arcs"]
        arc_list = []
        for arc in story_arc_credits:
            arc_list.append(arc["name"])
        if arc_list:
            metadata.story_arc = list_to_string(arc_list)

        return metadata
