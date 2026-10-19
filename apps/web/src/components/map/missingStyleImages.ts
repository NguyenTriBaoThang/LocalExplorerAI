type MapImageHost = {
  on(event: 'styleimagemissing', listener: (event: { id?: string }) => void): unknown
  off(event: 'styleimagemissing', listener: (event: { id?: string }) => void): unknown
  hasImage(id: string): boolean
  addImage(id: string, image: ImageData, options?: { pixelRatio?: number }): unknown
}

/** Goong's shared style may reference this sprite even when its sprite sheet omits it. */
export function installMissingStyleImageFallback(map: MapImageHost): () => void {
  const addMountainFallback = (event: { id?: string }) => {
    if (event.id !== 'mountain-11' || map.hasImage(event.id)) return

    const size = 32
    const canvas = document.createElement('canvas')
    canvas.width = size
    canvas.height = size
    const context = canvas.getContext('2d', { willReadFrequently: true })
    if (!context) return

    context.fillStyle = '#64748b'
    context.beginPath()
    context.moveTo(2, 27)
    context.lineTo(11, 10)
    context.lineTo(17, 19)
    context.lineTo(22, 12)
    context.lineTo(30, 27)
    context.closePath()
    context.fill()
    context.fillStyle = '#cbd5e1'
    context.beginPath()
    context.moveTo(11, 10)
    context.lineTo(15, 16)
    context.lineTo(12, 15)
    context.lineTo(10, 17)
    context.closePath()
    context.fill()

    map.addImage(event.id, context.getImageData(0, 0, size, size), { pixelRatio: 2 })
  }

  map.on('styleimagemissing', addMountainFallback)
  return () => map.off('styleimagemissing', addMountainFallback)
}
