from time import sleep

import streamlit as st

from src.page.ui_lib.page_util import PageUtil
from src.page.ui_lib.shared_bridge_settings import select_image_tags_from_ecr_cache
from src.k8s_client import K8sClient
from src.models import AppSettings
from src.task.k8s_autosizing_task import K8S_TASK

ecr_image_tags = None

@st.dialog("Edit AutoScale Settings", width="large")
def edit_autoscale_settings(app: AppSettings):
    with st.spinner("fetching images from ecr ..."):
        image_tag, is_valid = select_image_tags_from_ecr_cache(st.container())
        # image_tag, is_valid = select_image_tags_from_ecr(app, st.container(), True)

    replica_count = st.number_input("replica count:", value=app.autoscale_replica_count, placeholder="enter number of pods")
    replica_count = int(replica_count)
    check_interval_hours = st.text_input("Check autoscale pod count every (hours):", app.autoscale_check_interval_hours)

    is_disabled = True
    if (replica_count != app.autoscale_replica_count
            or check_interval_hours != app.monitor_check_interval_hours
            or image_tag != app.autoscale_img_tag):
        is_disabled = False
    if st.button("Save", disabled=is_disabled):
        app.autoscale_replica_count = int(replica_count)
        app.autoscale_check_interval_hours = float(check_interval_hours)
        app.autoscale_img_tag = image_tag
        K8S_TASK.set_params(app)
        app.save()
        st.success("saved")
        sleep(1)
        st.rerun()


def page_content():
    st.info(f"""
    The autoscale job will run continuously in the background and check if the expected number of pod replicas are running and spin up or spin down pods as needed.
    You can define the bridge settings like pool on the run page.
    One PAT token will be used per bridge container. These should be sufficient PAT tokens available in config/bridge_tokens.yml.
    If a bridge pod becomes disconnected because of a bad PAT token then the pod will be removed and a new pod with a new token will be spun up to replace it. """)
    is_alive = K8S_TASK.check_status()
    app = AppSettings.load_static()
    status = "running" if is_alive else "stopped"

    col1, col2 = st.columns(2)
    col1.markdown(f"AutoScale Job Status: `{status}`")
    if col2.button("Edit"):
        edit_autoscale_settings(app)
    col1.markdown(f"Image Tag: `{app.autoscale_img_tag}`")
    col1.markdown(f"Replica count: `{app.autoscale_replica_count}`")
    col1.markdown(f"Check status every: `{app.autoscale_check_interval_hours}` hours")
    col1.markdown("---")

    if not is_alive:
        if st.button("Start AutoScale Job"):
            with st.spinner("starting ..."):
                k8s_client = K8sClient()
                status = k8s_client.check_connection()
                if not status.can_connect:
                    st.error(f"Can't connect to kubernetes. {status.error}")
                    return
                K8S_TASK.set_params(app)
                K8S_TASK.start()
                st.success("Autoscale Started")
                sleep(1)
                st.rerun()
    else:
        if st.button("Stop AutoScale Job"):
            with st.spinner("stopping ..."):
                K8S_TASK.stop()
                st.warning("Monitoring Stopped")
                sleep(.5)
                st.rerun()

    st.markdown(f"Last time run: `{K8S_TASK.last_run}`")
    if K8S_TASK.last_message:
        st.markdown("Last message:")
        cont = st.container(border=True)
        cont.text(f"{K8S_TASK.last_message}")

    if st.button("🔄"):
        st.rerun()

PageUtil.set_page_config("AutoScale Bridge Pods", ":material/unfold_more: AutoScale Bridge Pods", True)
page_content()
