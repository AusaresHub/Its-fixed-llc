# It's Fixed Ltd site

Static marketing site for `itsfixedltd.com`, structured for direct Dokploy deployment.

## Files

- `index.html`: landing page markup
- `styles.css`: site styling
- `script.js`: scroll reveal behavior
- `Dockerfile`: container build for Dokploy
- `nginx.conf`: static site server config

## Dokploy deployment

1. Push this folder into the `its-fixed-llc` GitHub repository.
2. In Dokploy, create an application from that repository.
3. Use the included `Dockerfile`.
4. Set the domain to `itsfixedltd.com`.
5. Expose port `80`.

## Notes

- The page is inspired by the conversion structure of `ueni.com`, but the implementation and copy are original.
- Replace `hello@itsfixedltd.com` if you want a different contact route.
