from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List

import yaml

from deployment.github_release_util import GithubReleaseUtil
from src.github_version_checker import GithubVersionChecker


@dataclass
class ReleaseMetric:
    version: str
    count_zip_downloads: int
    date: str = None
    app_version_downloads: int = 0
    bridgectl_setup_downloads: int = 0

@dataclass
class SetupMetric:
    date: str = datetime.now().strftime("%Y-%m-%d")
    app_version_downloads: int = None
    bridgectl_setup_downloads: int = None
    new_release_version: str = None

@dataclass
class MetricsData:
    total_dot_release_zip_downloads: int
    total_bridgectl_setup_downloads: int
    total_app_version_downloads: int
    dot_releases: List[ReleaseMetric]
    # setup_releases: List[SetupMetric]

class DeployMetrics:
    def __init__(self, target_env, gh: GithubReleaseUtil):
        self.target_env = target_env
        self.gh = gh

    def metrics_filename(self):
        return Path(__file__).parent / "metrics" / f"metrics_{self.target_env}.yaml"

    def save_metrics(self, release: ReleaseMetric):
        md = self.load()
        # setup.new_release_version = release.version
        last = md.dot_releases[-1] if md.dot_releases else None
        if last and last.version == release.version:
            md.dot_releases.pop()
            # md.setup_releases.pop()
            print(f"    (replacing metrics for last version)")
        print("\nTotals:")
        md.dot_releases.append(release)
        # md.setup_releases.append(setup)
        md.total_dot_release_zip_downloads = 0
        for r in md.dot_releases:
            md.total_dot_release_zip_downloads += r.count_zip_downloads
        md.total_bridgectl_setup_downloads = 0
        md.total_app_version_downloads = 0
        for s in md.dot_releases:
            md.total_bridgectl_setup_downloads += s.bridgectl_setup_downloads
            md.total_app_version_downloads += s.app_version_downloads
        print("totals for dot_releases:")
        print("    total asset downloads (zip packages):", md.total_dot_release_zip_downloads)
        print("totals for setup_release: ")
        print("    bridgectl_setup.py downloads:", md.total_bridgectl_setup_downloads)
        print("    app_version.yaml downloads:", md.total_app_version_downloads)
        print()
        self.save(md)
        print("\nmetrics saved")

    def load(self)-> MetricsData:
        p = self.metrics_filename()
        if not p.exists():
            content = {
                "dot_releases":[],
                "setup_releases": [],
                "total_release_zip_downloads": 0,
                "total_bridgectl_setup_downloads": 0,
                "total_app_version_downloads": 0
            }
        else:
            with open(p, 'r') as f:
                content = yaml.load(f, Loader=yaml.FullLoader)
        md = MetricsData(**content)
        md.dot_releases = []
        for r in content['dot_releases']:
            r = ReleaseMetric(**r)
            md.dot_releases.append(r)
        # md.setup_releases = []
        # for s in content['setup_releases']:
        #     s = SetupMetric(**s)
        #     md.setup_releases.append(s)
        return md

    def save(self, data: MetricsData):
        with open(self.metrics_filename(), 'w') as outfile:
            save_data = asdict(data)
            yaml.dump(save_data, outfile, default_flow_style=False, sort_keys=False)

    def get_metrics(self):
        print(f"RELEASE: {GithubVersionChecker.SETUP_RELEASE}")
        setup_release = self.gh.get_release_by_tag(GithubVersionChecker.SETUP_RELEASE)
        if not setup_release:
            print("setup release not found")
            return
        setup_metric = SetupMetric()
        for asset in setup_release.get_assets():
            if asset.name == "bridgectl_setup.py":
                setup_metric.bridgectl_setup_downloads = asset.download_count
            elif asset.name == "app_version.yml":
                setup_metric.app_version_downloads = asset.download_count
            print(f"{asset.name}: {asset.download_count}")
        names = self.gh.list_releases()
        total_downloads = 0
        release_metric = None
        save_first = True
        n = 2
        for count, name in enumerate(names, 1):
            if name == GithubVersionChecker.SETUP_RELEASE:
                continue
            print(f"\nRELEASE: {name}")
            release = self.gh.get_release_by_tag(name)
            for asset in release.get_assets():
                if asset.name.endswith(".zip"):
                    total_downloads += asset.download_count
                print(f"{asset.name}: {asset.download_count}")
                if not release_metric:
                    release_metric = ReleaseMetric(name, asset.download_count)
                else:
                    release_metric.count_zip_downloads += asset.download_count
            if not release_metric.date:
                release_metric.date = datetime.now().strftime("%Y-%m-%d")
                release_metric.bridgectl_setup_downloads = setup_metric.bridgectl_setup_downloads
                release_metric.app_version_downloads = setup_metric.app_version_downloads
            if save_first:
                self.save_metrics(release_metric)
                save_first = False
            if count > n:
                break
