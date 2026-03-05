FROM ubuntu:24.04

RUN apt update \
  && apt -y upgrade \
  && apt install -y build-essential libc6-dev libc6-dev-i386 \
    gcc-multilib g++-multilib clang python3 python3-pip python3-venv cmake
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install xlsxwriter pycryptodome defusedxml pyyaml matplotlib

WORKDIR /cb-multios
COPY . ./

RUN ["/bin/bash", "./build.sh"]

ENTRYPOINT "/bin/bash"
