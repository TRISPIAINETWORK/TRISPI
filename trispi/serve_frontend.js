const http = require("http");
const fs = require("fs");
const path = require("path");
const PORT = process.env.PORT || 5001;

const DIST = path.join(__dirname, "frontend", "dist");
if (!fs.existsSync(path.join(DIST, "index.html"))) {
  const alt = path.join(__dirname, "frontend", "build");
  if (!fs.existsSync(path.join(alt, "index.html"))) {
    console.error("No frontend build found!"); process.exit(1);
  }
}

const MIME = {
  ".html": "text/html", ".js": "application/javascript",
  ".css": "text/css", ".json": "application/json",
  ".png": "image/png", ".jpg": "image/jpeg", ".svg": "image/svg+xml",
  ".ico": "image/x-icon", ".woff2": "font/woff2", ".woff": "font/woff",
  ".pdf": "application/pdf", ".txt": "text/plain", ".xml": "application/xml",
};

// Script injected into every index.html response so the CRA app picks up the
// correct API base at runtime without requiring a rebuild.
const API_INJECTION = `<script>window.TRISPI_API_BASE="/api";window.TRISPI_WS_BASE=(location.protocol==="https:"?"wss:":"ws:")+"//"+ location.host;</script>`;

const server = http.createServer((req, res) => {
  let urlPath = req.url.split("?")[0];

  // Serve whitepaper — PDF if available, else HTML
  if (urlPath === "/whitepaper" || urlPath === "/whitepaper.pdf" || urlPath === "/whitepaper.html") {
    const pdfPath  = path.join(__dirname, "docs", "TRISPI_Whitepaper.pdf");
    const htmlPath = path.join(__dirname, "docs", "TRISPI_Whitepaper.html");
    if (fs.existsSync(pdfPath)) {
      const stat = fs.statSync(pdfPath);
      res.setHeader("Content-Type", "application/pdf");
      res.setHeader("Content-Disposition", 'inline; filename="TRISPI_Whitepaper_v3.0.pdf"');
      res.setHeader("Content-Length", stat.size);
      res.setHeader("Access-Control-Allow-Origin", "*");
      fs.createReadStream(pdfPath).pipe(res);
      return;
    }
    if (fs.existsSync(htmlPath)) {
      const content = fs.readFileSync(htmlPath, "utf8");
      res.setHeader("Content-Type", "text/html; charset=utf-8");
      res.setHeader("Content-Length", Buffer.byteLength(content));
      res.setHeader("Access-Control-Allow-Origin", "*");
      res.end(content);
      return;
    }
  }

  let filePath = path.join(DIST, urlPath);

  res.setHeader("Access-Control-Allow-Origin", "*");

  if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
    filePath = path.join(DIST, "index.html");
  }

  const ext = path.extname(filePath);
  res.setHeader("Content-Type", MIME[ext] || "application/octet-stream");

  // Inject runtime config into HTML files so no rebuild is needed when the
  // deployment domain changes.
  if (ext === ".html" || filePath.endsWith("index.html")) {
    const content = fs.readFileSync(filePath, "utf8");
    const injected = content.replace("</head>", API_INJECTION + "</head>");
    res.setHeader("Content-Length", Buffer.byteLength(injected));
    res.end(injected);
    return;
  }

  fs.createReadStream(filePath).pipe(res);
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`TRISPI Frontend running at http://0.0.0.0:${PORT}`);
});
