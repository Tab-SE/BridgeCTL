from time import sleep

import streamlit as st

from src.models import AppSettings


class LoginManager:
    @staticmethod
    def check_login(app: AppSettings):
        if not app.login_password_for_bridgectl: # no password is set up.
            return True

        if 'logged_in' not in st.session_state:
            st.session_state['logged_in'] = False

        if st.session_state['logged_in']:
            return True
        else:
            st.title("BridgeCTL Login")
            with st.form(key='login_form'):
                pwd = st.text_input("Enter password", type="password", help="This password can be modified by editing application settings.")
                if st.form_submit_button(label='Login'):
                    if pwd == app.login_password_for_bridgectl:
                        st.session_state['logged_in'] = True
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        st.error("Incorrect password. Please try again.")

                    # pg = st.navigation(pages) #futuredev: maybe move to separate page.
                    # pg.run()
            return False

    @staticmethod
    def update_login(app: AppSettings, cont):
        cont.markdown("#### Login")
        cont.info("Set a password to protect access to the BridgeCTL User Interface")
        if app.login_password_for_bridgectl:
            cont.caption(f"A login password has been added")
            if cont.button("Logout"):
                st.session_state['logged_in'] = False
                st.rerun()
        else:
            cont.caption(f"No login password added")
        w = "Change" if app.login_password_for_bridgectl else "Add"
        with cont.expander(f"{w} password"):
            with st.form(key='login_form', border=False):
                pwd = st.text_input("Password", type="password")
                if st.form_submit_button("Save"):
                    st.session_state['logged_in'] = False
                    app.login_password_for_bridgectl = pwd
                    app.save()
                    st.success("saved")
                    sleep(.7)
                    st.rerun()
            if app.login_password_for_bridgectl:
                if st.button("Remove password"):
                    app.login_password_for_bridgectl = ""
                    app.save()
                    st.success("Password removed")
                    sleep(.7)
                    st.rerun()
