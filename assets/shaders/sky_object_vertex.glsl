#version 330 core
layout (location = 0) in vec2 aPos; // -1..1 квад в локальном пространстве billboard'а

out vec2 vLocalPos;

uniform mat4 view;
uniform mat4 projection;
uniform vec3 center; // camera_position + direction * distance
uniform vec3 right;  // camera right * размер диска
uniform vec3 up;     // camera up * размер диска

void main() {
    vLocalPos = aPos;
    vec3 world_pos = center + right * aPos.x + up * aPos.y;
    gl_Position = projection * view * vec4(world_pos, 1.0);
}
