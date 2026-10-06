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

    // aNormal.x = 1 отмечает верхние вершины куста (см. Chunk.cpp::add_flora_block_data) —
    // не настоящая нормаль (у X-style флоры её как таковой нет), а флаг "качать на ветру".
    // Пробовали различать через UV (v_min/v_max), но v_max одного тайла атласа численно
    // совпадает с v_min соседнего (тайлы стыкуются впритык) — при точном значении на границе
    // тайла нельзя надёжно определить, какому из двух тайлов оно "принадлежит". Через нормаль
    // такой неоднозначности нет вообще.
    bool is_top = aNormal.x > 0.5;

    if (is_top) {
        // Низ куста/цветка остаётся на месте (растение "укоренено"), качается только
        // верх — как трава/цветы на ветру. floor(pos.xz) даёт разную фазу для двух верхних
        // углов одного куста (они стоят по диагонали), так что крест слегка "штопорит", а не
        // переносится идеально параллельно — на глаз это больше похоже на естественное
        // трепетание листвы, чем на баг, так что решили не усложнять шейдер ради идеальной
        // синхронности через дополнительный vertex-атрибут.
        vec2 anchor = floor(pos.xz);
        float phase = anchor.x * 1.7 + anchor.y * 1.3;
        float sway = sin(time * 1.8 + phase) * 0.09;
        pos.x += sway;
        pos.z += sway * 0.6;
    }

    FragPos = pos;
    Normal = vec3(0.0, 1.0, 0.0); // настоящая нормаль для освещения — см. комментарий выше про aNormal.x
    TexCoord = aTexCoord;
    BlockLight = aLight;
    gl_Position = projection * view * model * vec4(pos, 1.0);
}
