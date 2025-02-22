#!/bin/bash

# 设置 PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(pwd)

# 运行传入的 alembic 命令
alembic "$@" 