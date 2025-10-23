Frontend (Vue CDN + PDF.js)

Local Preview
- Open `frontend/index.html` directly in a browser (no build needed).
- Set `API_BASE_URL` in `frontend/config.js` to your API Gateway base URL output from the stack.

Upload to S3 Static Website
1) Ensure the CloudFormation stack outputs `StaticSiteURL` and created the site bucket.
2) Run `./upload_frontend.sh` to sync the `frontend/` folder.
3) Open the StaticSiteURL to use the app.

Notes
- PDF text highlighting works best when the model returns exact snippets present on a single text span. Multi-span matches are partially supported.
- The app reads the selected PDF locally for the preview; uploads the same file to S3 for backend analysis.

