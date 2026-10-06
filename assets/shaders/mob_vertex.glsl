#version 330 core
layout (location = 0) in vec3 aPos;
layout (location = 1) in vec3 aNormal;
layout (location = 2) in vec2 aTexCoord;
layout (location = 3) in ivec4 aJointIndices;
layout (location = 4) in vec4 aJointWeights;

out vec2 TexCoord;
out vec3 Normal;
out vec3 FragPos;

uniform mat4 model;
uniform mat4 view;
uniform mat4 projection;

// Должно совпадать с MAX_MOB_BONES в src/mobs/Mob_Model.h
#define MAX_MOB_BONES 64
uniform mat4 bones[MAX_MOB_BONES];
// 0 — статичный меш без скелета (bones не используется), 1 — обычный skinning.
uniform int has_skin;

void main() {
    vec4 local_pos = vec4(aPos, 1.0);
    vec3 local_normal = aNormal;

    if (has_skin == 1) {
        mat4 skin_matrix =
            bones[aJointIndices.x] * aJointWeights.x +
            bones[aJointIndices.y] * aJointWeights.y +
            bones[aJointIndices.z] * aJointWeights.z +
            bones[aJointIndices.w] * aJointWeights.w;

        local_pos = skin_matrix * local_pos;
        local_normal = mat3(skin_matrix) * aNormal;
    }

    vec4 world_pos = model * local_pos;
    FragPos = world_pos.xyz;
    Normal = mat3(transpose(inverse(model))) * local_normal;
    TexCoord = aTexCoord;

    gl_Position = projection * view * world_pos;
}
