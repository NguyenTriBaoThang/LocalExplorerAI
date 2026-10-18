export const webOrigin = ['localhost', '127.0.0.1'].includes(location.hostname)
  ? `${location.protocol}//${location.hostname}:8080`
  : location.hostname === 'portal.localexplorerai.site'
    ? 'https://www.localexplorerai.site'
    : location.origin
