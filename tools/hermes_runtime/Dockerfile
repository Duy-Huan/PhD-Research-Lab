# Upstream Hermes0.22.5, bf0203a794a07aac3ff764972ab9087baa4e4f4e.
# No source from the PhD Lab repository is sent to this build except this adapter.
FROM nousresearch/hermes-agent@sha256:9c5561579f3ffdf333401797094ac3a743738d6c25d40f4331c7bf77b694238d
COPY service.py proxy.mjs cli_egress_proxy.mjs /opt/phdlab-runtime/
LABEL phdlab.runtime="hermes" phdlab.rpc.version="1" phdlab.hermes.revision="bf0203a794a07aac3ff764972ab9087baa4e4f4e"
# Reuse the upstream declared volume destination, preventing an extra anonymous data volume.
ENV HERMES_HOME=/opt/data HOME=/opt/data HERMES_WRITE_SAFE_ROOT=/opt/data PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace
USER 1000:1000
ENTRYPOINT ["/opt/hermes/.venv/bin/python", "/opt/phdlab-runtime/service.py"]
