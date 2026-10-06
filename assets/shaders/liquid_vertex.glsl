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
uniform float time;

void main() {
    vec3 pos = aPos;

    // Волна только на верхней грани жидкости (нормаль смотрит вверх) — боковые и нижние
    // грани не трогаем, иначе появятся щели со стенками соседних твёрдых блоков (вода
    // "оторвётся" от берега/дна).
    if (aNormal.y > 0.5) {
        float wave = sin(pos.x * 0.7 + time * 1.3) * 0.035
                   + cos(pos.z * 0.6 + time * 1.7) * 0.035;
        pos.y += wave;
    }

    FragPos = pos;
    Normal = aNormal;
    TexCoord = aTexCoord;
    BlockLight = aLight;
    gl_Position = projection * view * model * vec4(pos, 1.0);
}
