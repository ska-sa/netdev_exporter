ARG KATSDPDOCKERBASE_REGISTRY=harbor.sdp.kat.ac.za/dpp

FROM $KATSDPDOCKERBASE_REGISTRY/docker-base-build as build

# Enable Python 3 venv
ENV PATH="/home/kat/.local/bin:$PATH_PYTHON3" VIRTUAL_ENV="$VIRTUAL_ENV_PYTHON3"

# Install Python dependencies
COPY --chown=kat:kat requirements.txt /tmp/install/requirements.txt
RUN uv pip compile /tmp/install/requirements.txt \
    -c /home/kat/docker-base/base-requirements.lock \
    -o /tmp/install/requirements.lock && \
    uv pip install --no-deps \
    -r /tmp/install/requirements.lock && \
    uv pip check

# Install the current package
COPY --chown=kat:kat . /tmp/install/netdev_exporter

RUN cd /tmp/install/netdev_exporter && \
    uv pip install --no-deps . && uv pip check

#######################################################################

FROM $KATSDPDOCKERBASE_REGISTRY/docker-base-runtime
LABEL maintainer=sdpdev+netdev_exporter@ska.ac.za

# Install ethtool and ibdev2netdev
USER root
RUN apt-get update && apt-get -y install ethtool && apt-get clean
COPY ibdev2netdev /usr/bin/
USER kat

COPY --chown=kat:kat --from=build /home/kat/ve3 /home/kat/ve3
ENV PATH="/home/kat/.local/bin:$PATH_PYTHON3" VIRTUAL_ENV="$VIRTUAL_ENV_PYTHON3"

EXPOSE 9117
ENTRYPOINT ["/sbin/tini", "--", "netdev-exporter"]
