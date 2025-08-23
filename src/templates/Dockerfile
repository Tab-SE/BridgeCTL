FROM #<FROM_BASEIMAGE>

RUN mkdir -p /bridge_setup
WORKDIR /bridge_setup

#<USER_CREATE>

#<Locale_Setup>

COPY start-bridgeclient.sh drivers_download.sh drivers_install.sh /bridge_setup/
#<COPY_DRIVER_FILES>

ARG IS_RELEASE
RUN cd /bridge_setup && chmod +x *.sh && \
    ./drivers_download.sh && \
    ./drivers_install.sh && \
    rm -rf /tmp/driver_caddy

ARG BRIDGERPM
COPY $BRIDGERPM /bridge_setup/
RUN cd /bridge_setup && chmod +x $BRIDGERPM && ACCEPT_EULA=y yum localinstall -y $BRIDGERPM && rm -f $BRIDGERPM

#<COPY_BridgeClientConfiguration>
USER #<USER_NAME>

CMD ["./start-bridgeclient.sh"]
