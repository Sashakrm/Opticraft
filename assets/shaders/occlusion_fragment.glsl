#version 330 core
out vec4 FragColor;

void main() {
    // glColorMask is disabled while this is bound (see Renderer::render_chunks), so the
    // value written here never reaches the framebuffer — only the depth test matters.
    FragColor = vec4(1.0);
}
