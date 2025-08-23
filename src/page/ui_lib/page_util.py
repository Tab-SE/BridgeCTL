import streamlit as st

from src.cli.app_config import APP_CONFIG
from src.enums import ContainerRepoURI
from src.lib.general_helper import StringUtils
from src.models import LoggerInterface
from src.token_loader import TokenLoader


class PageUtil:
    @staticmethod
    def set_page_config(page_title: str, page_header: str = None, skip_image: bool = False):
        title =  f"{page_title}" if page_title else "Tableau Bridge"
        st.logo("src/page/assets/tableau_icon_24.png")
        st.set_page_config(
            page_title=title,
            page_icon="📊",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        PageUtil.set_tableau_styles()
        if not page_header:
            page_header = title
        if page_header != PageUtil.NO_PAGE_HEADER:
            st.write(f"# {page_header}")
        if skip_image:
            return

    @staticmethod
    def set_tableau_styles():
        st.html(
            """
            <style>
            /* Headings */
            /*
            *.stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
                font-weight: 600;
            }*/

            /* Buttons - subtle outline style */
            .stButton button {
                background-color: #FFF;
                color: #333;
                border: 1px solid #C9C9C9;
                border-radius: 4px;
                padding: 0.3rem 0.75rem;
                font-weight: 500;
            }
            /* Hover style: gray background, dark text */
            .stButton button:hover {
                background-color: #BFBFBF;
                color: #333333;
                cursor: pointer;
            }

            /* Tables */
            .stDataFrame, .stTable, .stDataFrameContainer {
                border: 1px solid #EDEDED;
                border-radius: 4px;
                margin-bottom: 1rem;
            }
            .stDataFrame table thead tr th {
                background-color: #F8F8F8;
                font-weight: 600;
                border-bottom: 1px solid #EDEDED;
                padding: 0.5rem 0.75rem;
                color: #333;
            }
            .stDataFrame table tbody tr td {
                padding: 0.5rem 0.75rem;
                border-bottom: 1px solid #F0F0F0;
            }
            </style>
            """
        )

    @staticmethod
    def horizontal_radio_style():
        st.html(
            """<style>div[data-testid="stRadio"] > div {
                    display: flex;
                    flex-direction: row;
                }
                div[data-testid="stRadio"] label {
                    margin-right: 1rem;
                }</style>
                """)

    @staticmethod
    def get_base_image_examples():
        base_image_examples = ", ".join(StringUtils.get_values_from_class(ContainerRepoURI))
        if APP_CONFIG.is_internal_build():
            from src.internal.devbuilds.devbuilds_const import ReposDev
            base_image_examples += f", {ReposDev.sfdc_rhel9}"
        return base_image_examples

    @staticmethod
    def get_admin_pat_or_log_error(logger: LoggerInterface):
        token = TokenLoader(logger).get_token_admin_pat()
        if not token:
            logger.warning("You can add PAT tokens on the [Settings page](/Settings)")
            return None
        return token

    NO_PAGE_HEADER = "NO_HEADER"