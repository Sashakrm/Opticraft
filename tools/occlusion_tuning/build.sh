#!/usr/bin/env bash
# Собирает occlusion_test отдельно от движка, но с реальным GLFW/OpenGL (не заглушка) —
# использует ../../external/glad (как основной проект) + системные glfw3/glm через pkg-config.
# Нужны пакеты: libglfw3-dev, libglm-dev, libgl1-mesa-dev (или проприетарный драйвер).
set -euo pipefail
cd "$(dirname "$0")"

GLAD_DIR=../../external/glad
g++ -std=c++17 -O2 \
  -I "$GLAD_DIR/include" \
  occlusion_test.cpp "$GLAD_DIR/src/gl.c" \
  $(pkg-config --cflags --libs glfw3) -lGL -ldl \
  -o occlusion_test

echo "Собрано: tools/occlusion_tuning/occlusion_test"
