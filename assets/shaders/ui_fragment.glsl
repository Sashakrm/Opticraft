#version 330 core
in vec2 vUV;
in vec4 vColor;
out vec4 FragColor;

uniform sampler2D atlas;

void main() {
    vec4 t = texture(atlas, vUV);
    FragColor = t * vColor;
    if (FragColor.a < 0.004) discard;
}
