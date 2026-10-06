#version 330 core
layout (location = 0) in vec3 aPos;
layout (location = 1) in vec2 aTexCoord;
layout (location = 2) in vec3 aNormal;
layout (location = 3) in float aLight;

out vec2 TexCoord;
out vec3 Normal;
out vec3 FragPos;
out float BlockLight;

uniform mat4 model;
uniform mat4 view;
uniform mat4 projection;

void main() {
    FragPos = aPos;
    Normal = aNormal;
    TexCoord = aTexCoord;
    BlockLight = aLight;
    gl_Position = projection * view * model * vec4(aPos, 1.0);
}