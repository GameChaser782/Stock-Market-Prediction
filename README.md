# Portfolio Analyzer

AI-powered portfolio analysis tool. Try it live: **https://gamechaser782.github.io/Portfolio-Analyser/**

## Features
- **@ Mention Stocks**: Type `@AAPL` or `@reliance` to add stocks
- **Multi-Currency**: ₹ for Indian stocks, $ for US stocks
- **AI Analysis**: Get a 1-100 score with detailed reasoning
- **No Backend Required**: Runs entirely in the browser

## How to Use
1. Visit the live site or open `index.html` locally
2. Get a free Gemini API key at [ai.google.dev](https://ai.google.dev)
3. Enter your API key (stored only in your browser session)
4. Type `@` to search for stocks
5. Click "Analyze Portfolio"

## Supported Stocks
- **US**: AAPL, MSFT, GOOGL, AMZN, TSLA, META, NVDA, NFLX
- **India**: RELIANCE, TCS, INFY, HDFCBANK, MARUTI, BHARTIARTL, ICICIBANK, SBIN, etc.

## GitHub Pages Setup
1. Push this repo to GitHub
2. Go to Settings → Pages
3. Set Source to "Deploy from a branch"
4. Select `main` branch and `/ (root)` folder
5. Save and wait for deployment

## Files
- `index.html` - Complete app (for GitHub Pages)
- `backend/` - Flask server version (for local development)

## Privacy
- Your API key is stored only in your browser's session storage
- Keys are never sent to any server except Google's Gemini API
- No data is collected or stored
