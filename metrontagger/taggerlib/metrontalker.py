import json
import platform
from datetime import datetime
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from metrontagger.comicapi.genericmetadata import GenericMetadata
from metrontagger.comicapi.issuestring import IssueString
from metrontagger.comicapi.utils import listToString

from .. import version


class MetronTalker:
    def __init__(self, auth):
        self.api_base_url = "https://metron.cloud/api"
        self.auth_str = f"Basic {auth.decode('utf-8')}"
        self.user_agent = (
            f"Metron-Tagger/{version} ({platform.system()}; {platform.release()})"
        )

    def parseDateStr(self, date_str):
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

    def fetch_response(self, url):
        request = Request(url)
        request.add_header("Authorization", self.auth_str)
        request.add_header("User-Agent", self.user_agent)

        try:
            content = urlopen(request)
        except HTTPError as e:
            print(e)
            print(e.headers)

        resp = json.loads(content.read().decode("utf-8"))

        return resp

    def fetchIssueDataByIssueID(self, issue_id):
        url = self.api_base_url + f"/issue/{issue_id}/?format=json"
        resp = self.fetch_response(url)

        return self.mapCVDataToMetadata(resp)

    def searchForIssue(self, series, num, year):
        url = self.api_base_url + f"/issue/?series_name={series}&number={num}"
        if year:
            url += f"&cover_year={year}"
        url += "&format=json"
        resp = self.fetch_response(url)

        return resp

    def mapCVDataToMetadata(self, issue_results):
        metadata = GenericMetadata()

        metadata.series = issue_results["series"]

        num_s = IssueString(issue_results["number"]).asString()

        metadata.issue = num_s

        titles = issue_results["name"]
        title_list = []
        for title in titles:
            title_list.append(title)
        metadata.title = listToString(title_list)

        metadata.day, metadata.month, metadata.year = self.parseDateStr(
            issue_results["cover_date"]
        )

        metadata.comments = issue_results["desc"]

        d = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        metadata.notes = (
            f"Tagged with MetronTagger-{version} using info from Metron on {d}. "
            + f"[issue_id:{issue_results['id']}]"
        )

        person_credits = issue_results["credits"]
        for person in person_credits:
            if "role" in person:
                roles = person["role"]
                for role in roles:
                    metadata.addCredit(person["creator"], role["name"], False)

        character_credits = issue_results["characters"]
        character_list = []
        for character in character_credits:
            character_list.append(character["name"])
        metadata.characters = listToString(character_list)

        team_credits = issue_results["teams"]
        team_list = []
        for team in team_credits:
            team_list.append(team["name"])
        metadata.teams = listToString(team_list)

        story_arc_credits = issue_results["arcs"]
        arc_list = []
        for arc in story_arc_credits:
            arc_list.append(arc["name"])
        if len(arc_list) > 0:
            metadata.storyArc = listToString(arc_list)

        return metadata
