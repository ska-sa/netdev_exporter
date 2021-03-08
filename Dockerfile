ARG KATSDPDOCKERBASE_REGISTRY=quay.io/ska-sa

FROM $KATSDPDOCKERBASE_REGISTRY/docker-base-build as build

# Enable Python 3 venv
ENV PATH="$PATH_PYTHON3" VIRTUAL_ENV="$VIRTUAL_ENV_PYTHON3"

# Install Python dependencies
COPY --chown=kat:kat requirements.txt /tmp/install/requirements.txt
RUN install_pinned.py -r /tmp/install/requirements.txt

# Install the current package
COPY --chown=kat:kat . /tmp/install/netdev_exporter

RUN cd /tmp/install/netdev_exporter && \
    ./setup.py clean && pip install --no-deps . && pip check

#######################################################################

FROM $KATSDPDOCKERBASE_REGISTRY/docker-base-runtime
LABEL maintainer=sdpdev+netdev_exporter@ska.ac.za

# Install ethtool and ibdev2netdev
USER root
RUN apt-get update && apt-get -y install ethtool && apt-get clean
COPY ibdev2netdev /usr/bin/
USER kat

COPY --chown=kat:kat --from=build /home/kat/ve3 /home/kat/ve3
ENV PATH="$PATH_PYTHON3" VIRTUAL_ENV="$VIRTUAL_ENV_PYTHON3"

EXPOSE 9117
ENTRYPOINT ["/sbin/tini", "--", "netdev-exporter"]
