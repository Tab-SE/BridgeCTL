import dataclasses
import os
from datetime import datetime
from typing import List

import yaml

from src.cli.app_logger import LOGGER
from src.enums import ADMIN_PAT_PREFIX, BridgeContainerName
from src.lib.general_helper import StringUtils
from src.models import PatToken, CONFIG_DIR, TokenSite, BridgeSiteTokens, PatTokenSecret, APP_STATE, CONFIG_BACKUP_DIR

token_file_path = CONFIG_DIR / "bridge_tokens.yml"
token_file_prefix = "bridge_tokens_"
old_token_file_path = CONFIG_DIR / "tokens.yml"
backup_tokens_path = CONFIG_BACKUP_DIR / "bridge_tokens_old.yml"

class TokenLoader:
    def __init__(self, logger):
        self.logger = logger

    def load(self) -> BridgeSiteTokens:
        if not os.path.exists(token_file_path):
            LOGGER.info(f"no tokens file found at {token_file_path}, creating new")
            self.create_new()
        with open(token_file_path) as f:
            content: dict = yaml.safe_load(f)
        bt = BridgeSiteTokens(
            tokens = [PatTokenSecret.from_dict(x) for x in content["tokens"]],
            site = TokenSite.from_dict(content["site"])
        )
        return bt

    def load_tokens(self) -> List[PatToken]:
        bst = self.load()
        return [PatToken(name=t.name, secret=t.secret, sitename=bst.site.sitename, pod_url=bst.site.pod_url, site_id=bst.site.site_id,
                         site_luid=bst.site.site_luid, user_email=bst.site.user_email, user_domain=bst.site.user_domain, pool_id=bst.site.pool_id, pool_name=bst.site.pool_name) for t in bst.tokens]

    @staticmethod
    def save(bst: BridgeSiteTokens):
        with open(token_file_path, "w") as f:
            yaml.dump(dataclasses.asdict(bst), f, sort_keys=False)

    def create_new(self):
        bst = BridgeSiteTokens(tokens=[], site=TokenSite(sitename="", pod_url="", site_id="", site_luid=""))
        self.save(bst)

    def save_token_file(self, tokens: List[PatToken]):
        bct = self.load()
        bct.tokens = [t.to_pat_token_secret() for t in tokens]
        self.save(bct)

    def get_token_admin_pat(self, tokens = None) -> PatToken:
        if not tokens:
            tokens = self.load_tokens()
        if not tokens:
            tokens = []
        admin_token = next((t for t in tokens if t.name.startswith(ADMIN_PAT_PREFIX)), None)
        if not admin_token:
            self.logger.warning(f"Please add a PAT Token starting with '{ADMIN_PAT_PREFIX}' to bridge_tokens.yml")
        return admin_token

    def get_token_by_name(self, token_name, throw_if_not_found = True) -> PatToken:
        tokens = self.load_tokens()
        if not tokens:
            if throw_if_not_found:
                raise Exception(f"No tokens found in {token_file_path}")
            return None
        for t in tokens:
            if t.name == token_name:
                return t
        return None

    @staticmethod
    def has_token_name(token_name: str, tokens: List[PatTokenSecret]) -> bool:
        for t in tokens:
            if t.name == token_name:
                return True
        return False

    def get_available_tokens(self, existing_container_names: List[str]) -> (List[str], List[str], List[PatToken]):
        tokens = self.load_tokens()
        if tokens is None:
            tokens = []
        available_token_names = []
        in_use_token_names = []
        for t in tokens:
            if t.is_admin_token():
                continue
            if BridgeContainerName.get_name(t.sitename, t.name) in existing_container_names:
                in_use_token_names.append(t.name)
            else:
                available_token_names.append(t.name)
        return available_token_names, in_use_token_names, tokens

    def remove_token(self, token_name: str):
        bst = self.load()
        bst.tokens = [t for t in bst.tokens if t.name != token_name]
        self.save(bst)

    def remove_token_and_archive(self, token_name: str):
        bst = self.load()
        old_token_secret = [t.secret for t in bst.tokens if t.name == token_name]
        if not old_token_secret:
            self.logger(f"token {token_name} not found in bridge_tokens.yml")
            return
        if not os.path.exists(backup_tokens_path):
            with open(backup_tokens_path, "w") as f:
                f.write("old_tokens:\n")
        old_token_yml = f"""  - sitename: {bst.site.sitename}
    pod_url: {bst.site.pod_url}
    token_name: {token_name}
    secret: {old_token_secret[0]},
    date_removed: {StringUtils.current_datetime_seconds()}\n"""
        with open(backup_tokens_path, "a") as f:
            f.write(old_token_yml)
        self.remove_token(token_name)

    def add_token(self, new_token: PatToken):
        bst = self.load()
        bst.site.sitename = new_token.sitename
        bst.site.pod_url = new_token.pod_url
        if new_token.site_luid:
            bst.site.site_luid = new_token.site_luid
        if new_token.site_id:
            bst.site.site_id = new_token.site_id
        if new_token.user_email:
            bst.site.user_email = new_token.user_email
        if new_token.user_domain:
            bst.site.user_domain = new_token.user_domain
        bst.tokens.append(new_token.to_pat_token_secret())
        self.save(bst)

    def update_token_site_ids(self, site_id: str, site_luid: str, user_email: str, user_domain: str):
        bst = self.load()
        bst.site.site_id = site_id
        bst.site.site_luid = site_luid
        bst.site.user_email = user_email
        bst.site.user_domain = user_domain
        self.save(bst)

    def update_pool_id(self, pool_id: str, pool_name: str):
        bst = self.load()
        bst.site.pool_id = pool_id
        bst.site.pool_name = pool_name
        self.save(bst)

    @staticmethod
    def have_additional_token_yml_site_files():
        for f in os.listdir(CONFIG_DIR):
            if f.startswith(token_file_prefix) and f.endswith(".yml"):
                return True
        return False

    @staticmethod
    def get_token_yml_site_list():
        site_list = []
        for f in os.listdir(CONFIG_DIR):
            if f.startswith(token_file_prefix) and f.endswith(".yml"):
                site = f.replace(token_file_prefix, "").replace(".yml", "")
                site_list.append(site)
        return site_list

    @classmethod
    def check_file_exists(cls, site_name):
        n = f"{token_file_prefix}{site_name}.yml"
        return os.path.exists(CONFIG_DIR / n)

    @classmethod
    def rename_token_file_to_site(cls, current_site):
        if not current_site:
            raise ValueError("current_site is required")
        n = f"{token_file_prefix}{current_site}.yml"
        os.rename(token_file_path, CONFIG_DIR / n)

    @classmethod
    def rename_token_file(cls, current_site, selected_site):
        cls.rename_token_file_to_site(current_site)
        selected_name = f"{token_file_prefix}{selected_site}.yml"
        os.rename(CONFIG_DIR / selected_name, token_file_path)

    def update_edge_manager_id(self, edge_manager_id: str, gw_api_token: str):
        bst = self.load()
        bst.site.edge_manager_id = edge_manager_id
        bst.site.gw_api_token = gw_api_token
        self.save(bst)


class TokenLoaderMigrate:
    @staticmethod
    def pat_token_from_dict(x: dict):
        return PatToken(name=x['name'], secret=x['secret'], sitename=x.get('sitename'), pod_url=x.get('pod_url'),
                        site_id=x.get('site_id'), site_luid=x.get('site_luid'))

    @staticmethod
    def migrate_tokens():
        if APP_STATE.migrated_tokens:
            return
        APP_STATE.migrated_tokens = True
        if not os.path.exists(old_token_file_path):
            return

        LOGGER.info(f"migrating old tokens from {old_token_file_path} to {token_file_path}")
        with open(old_token_file_path) as f:
            tokens: dict = yaml.safe_load(f)
        if not tokens:
            LOGGER.info(f"no tokens found in {old_token_file_path}, starting with blank tokens file")
            return
        admin_pat: PatToken = None
        # STEP - Get the admin token
        for item in tokens:
            p = TokenLoaderMigrate.pat_token_from_dict(item)
            if p.is_admin_token():
                admin_pat = p
                break
        if not admin_pat:
            admin_pat = TokenLoaderMigrate.pat_token_from_dict(tokens[0]) # grab the first token if no admin token found
        # STEP - get all other tokens
        ts = []
        msg = ""
        for item in tokens:
            p = TokenLoaderMigrate.pat_token_from_dict(item)
            if admin_pat.sitename == p.sitename:
                ts.append(p.to_pat_token_secret())
            else:
                m = f"token {p.name} site {p.sitename} is different than the admin_pat site {admin_pat.sitename}, skipping"
                msg += m + "\n"
                LOGGER.warning(m)

        bst = BridgeSiteTokens(tokens=ts, site=TokenSite(sitename=admin_pat.sitename, pod_url=admin_pat.pod_url, site_luid=admin_pat.site_luid, site_id=admin_pat.site_id))
        TokenLoader(None).save(bst)
        if not os.path.exists(CONFIG_BACKUP_DIR):
            os.makedirs(CONFIG_BACKUP_DIR)
        dte = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_tokens_file = CONFIG_BACKUP_DIR / f"tokens_{dte}.yml"
        old_token_file_path.rename(backup_tokens_file)
        return "success migrating tokens"

