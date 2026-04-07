const { readFileSync } = require('fs');
const { join } = require('path');

module.exports = (req, res) => {
  const html = readFileSync(join(__dirname, '..', 'install.html'), 'utf-8');
  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  res.setHeader('Cache-Control', 'no-cache, no-store');
  res.status(200).send(html);
};
