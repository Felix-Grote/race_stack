# syntax=docker/dockerfile:1
FROM ros:humble-ros-base-jammy@sha256:860e53793ccf575e5369b5e9a19939de2bfcfb46a299954d06f54f2af54fed19
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
# ROS tools/interfaces are supplied by the digest-pinned base. No driving stack.
RUN --mount=type=secret,id=system_ca,required=true \
    apt-get -o Acquire::https::CaInfo=/run/secrets/system_ca update && \
    apt-get -o Acquire::https::CaInfo=/run/secrets/system_ca install -y --no-install-recommends python3-venv=3.10.6-1~22.04.1 \
    python3.10-venv=3.10.12-1~22.04.18 \
    python3-pip-whl=22.0.2+dfsg-1ubuntu0.7 \
    python3-setuptools-whl=59.6.0-1.2ubuntu0.22.04.3 && \
    rm -rf /var/lib/apt/lists/*
RUN python3 -m venv --system-site-packages /opt/project-a
ENV PATH=/opt/project-a/bin:$PATH
COPY scripts/project_a/requirements*.lock /tmp/
# quadprog 0.1.7 is built from source against the declared Cython, without isolation.
RUN --mount=type=secret,id=system_ca,required=true \
    PIP_CERT=/run/secrets/system_ca python -m pip install --require-hashes -r /tmp/requirements.build.lock && \
    PIP_CERT=/run/secrets/system_ca python -m pip install --require-hashes --no-build-isolation -r /tmp/requirements.lock && \
    python -m pip check
ENV PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
WORKDIR /work
