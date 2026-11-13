import * as THREE from 'three'

/** The imported Meshy PBR mesh washes out under the map's outdoor lighting.
 * Its base-colour atlas already contains the painted roof, columns and trim. */
export function restorePalaceTexture(root: THREE.Object3D): void {
  root.traverse((node) => {
    if (!(node instanceof THREE.Mesh)) return
    const replace = (material: THREE.Material): THREE.Material => {
      if (!(material instanceof THREE.MeshStandardMaterial) ||
          material.name !== 'Meshy_Geunjeongjeon_PBR_0' || !material.map) return material
      return new THREE.MeshBasicMaterial({
        name: material.name,
        map: material.map,
        color: material.color,
        side: THREE.DoubleSide,
        toneMapped: false,
      })
    }
    node.material = Array.isArray(node.material) ? node.material.map(replace) : replace(node.material)
  })
}
