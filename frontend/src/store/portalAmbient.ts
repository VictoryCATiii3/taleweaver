import { ref } from 'vue'

/** RGB triplet of the genre accent currently hovered in the library; tints the portal backdrop. */
export const ambientAccent = ref<string | null>(null)

export function setAmbientAccent(rgb: string | null): void {
  ambientAccent.value = rgb
}
