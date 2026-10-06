#version 330 core
out vec4 FragColor;

in vec2 TexCoord;
in vec3 Normal;
in vec3 FragPos;
in float BlockLight;

uniform sampler2D textureAtlas;
uniform float ambient;
uniform float maxLightLevel;

void main() {
    // Та же простая модель освещения, что и в общем fragment.glsl — специально не меняем,
    // чтобы флора не начала визуально отличаться от твёрдых блоков освещением, только
    // покачиванием (см. flora_vertex.glsl).
    float light_intensity = 0.7f;
    if (Normal.y > 0.9) {
        light_intensity = 1.0f;
    } else if (Normal.y < -0.9) {
        light_intensity = 0.5f;
    }

    vec4 tex_color = texture(textureAtlas, TexCoord);
    if (tex_color.a < 0.1) {
        discard;
    }

    // BlockLight is a packed byte: low nibble = block light, high nibble = sky light.
    // Day/night affects ONLY skylight. Block lights remain bright inside caves at night.
    float packed_light = floor(BlockLight + 0.5);
    float block_light = mod(packed_light, 16.0);
    float sky_light = floor(packed_light / 16.0);
    float sky_scene_light = (sky_light / 15.0) * ambient;
    float block_scene_light = block_light / maxLightLevel;
    float scene_light = max(max(sky_scene_light, block_scene_light), 0.32);
    FragColor = vec4(tex_color.rgb * light_intensity * scene_light, tex_color.a);
}
