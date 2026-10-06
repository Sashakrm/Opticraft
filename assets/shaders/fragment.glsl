#version 330 core
out vec4 FragColor;

in vec2 TexCoord;
in vec3 Normal;
in vec3 FragPos;
in float BlockLight;

uniform sampler2D textureAtlas;
// Множитель дня/ночи (см. Day_Night_Cycle::get_ambient_intensity) — 1.0 днём, тусклее ночью.
uniform float ambient;
// Максимальный уровень света от блока (Config::max_light_level), для нормализации нижнего
// ниббла BlockLight; верхний ниббл хранит skylight (0..15).
uniform float maxLightLevel;

void main() {
    //  Простое освещение: яркость зависит от направления нормали
    float light_intensity = 0.7f;
    if (Normal.y > 0.9) {
        light_intensity = 1.0f;  // Верхняя грань — ярче
    } else if (Normal.y < -0.9) {
        light_intensity = 0.5f;  // Нижняя грань — темнее
    }

    //  Сэмплируем текстуру
    vec4 tex_color = texture(textureAtlas, TexCoord);

    // BlockLight is a packed byte: low nibble = block light, high nibble = skylight.
    // Day/night affects ONLY skylight. Block lights remain bright inside caves at night.
    float packed_light = floor(BlockLight + 0.5);
    float block_light = mod(packed_light, 16.0);
    float sky_light = floor(packed_light / 16.0);
    float sky_scene_light = (sky_light / 15.0) * ambient;
    float block_scene_light = block_light / maxLightLevel;
    // Не допускаем абсолютно чёрных поверхностей во время потокового обновления
    // light-данных: меш может быть отрисован на один кадр раньше нового skylight.
    float scene_light = max(max(sky_scene_light, block_scene_light), 0.32);

    //  Применяем освещение
    FragColor = vec4(tex_color.rgb * light_intensity * scene_light, tex_color.a);
}