# 📚 Article Scraper API - Integration Documentation

## 🎯 API Overview

**Live API URL:** `https://web-production-7ff5.up.railway.app/scrape`

Your article scraper API extracts structured data from news articles and returns it as JSON.

***

## 📋 API Endpoint

### Request Format
```
GET https://web-production-7ff5.up.railway.app/scrape?url=<ARTICLE_URL>
```

### Request Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | String | Yes | The full URL of the article to scrape |

### Example Request
```
https://web-production-7ff5.up.railway.app/scrape?url=https://www.thehindu.com/news/international/sharif-osman-hadi-murder-case-two-suspects-fled-to-india-bangladesh-police/article70445934.ece
```

***

## 📤 API Response Format

The API returns a JSON object with the following fields:

```json
{
  "authors": ["Author Name"],
  "images": ["image_url_1", "image_url_2", ...],
  "keywords": ["keyword1", "keyword2", ...],
  "text": "Full article content",
  "timestamp": "2025-12-28T15:06:42.000093",
  "title": "Article Title",
  "top_image": "featured_image_url"
}
```

### Response Fields Explained
| Field | Type | Description |
|-------|------|-------------|
| `authors` | Array | List of article author names |
| `images` | Array | URLs of all images in the article |
| `keywords` | Array | Article tags/keywords |
| `text` | String | Full article body content |
| `timestamp` | String | When the article was scraped (ISO format) |
| `title` | String | Article headline |
| `top_image` | String | URL of the featured/main image |

***

## 💻 Integration Examples

### 1. **JavaScript/Node.js**

```javascript
// Using Fetch API
async function getArticleData(articleUrl) {
  try {
    const apiUrl = `https://web-production-7ff5.up.railway.app/scrape?url=${encodeURIComponent(articleUrl)}`;
    
    const response = await fetch(apiUrl);
    const data = await response.json();
    
    console.log('Title:', data.title);
    console.log('Authors:', data.authors);
    console.log('Content:', data.text);
    console.log('Images:', data.images);
    
    return data;
  } catch (error) {
    console.error('Error fetching article:', error);
  }
}

// Usage
getArticleData('https://www.thehindu.com/news/...');
```

### 2. **React Application**

```jsx
import { useState, useEffect } from 'react';

function ArticleViewer({ articleUrl }) {
  const [article, setArticle] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchArticle = async () => {
      try {
        const response = await fetch(
          `https://web-production-7ff5.up.railway.app/scrape?url=${encodeURIComponent(articleUrl)}`
        );
        const data = await response.json();
        setArticle(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchArticle();
  }, [articleUrl]);

  if (loading) return <div>Loading article...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <article>
      <h1>{article.title}</h1>
      <p>By: {article.authors.join(', ')}</p>
      {article.top_image && <img src={article.top_image} alt="Featured" />}
      <div>{article.text}</div>
      <p>Tags: {article.keywords.join(', ')}</p>
    </article>
  );
}

export default ArticleViewer;
```

### 3. **Python (Flask/Django)**

```python
import requests

def get_article_data(article_url):
    api_url = 'https://web-production-7ff5.up.railway.app/scrape'
    params = {'url': article_url}
    
    try:
        response = requests.get(api_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        return {
            'title': data.get('title'),
            'authors': data.get('authors'),
            'content': data.get('text'),
            'images': data.get('images'),
            'top_image': data.get('top_image'),
            'keywords': data.get('keywords'),
            'timestamp': data.get('timestamp')
        }
    except requests.exceptions.RequestException as e:
        print(f"Error fetching article: {e}")
        return None

# Flask endpoint example
@app.route('/article', methods=['GET'])
def view_article():
    url = request.args.get('url')
    article_data = get_article_data(url)
    
    if article_data:
        return render_template('article.html', article=article_data)
    else:
        return "Failed to fetch article", 400
```

### 4. **Vue.js**

```vue
<template>
  <div class="article-container">
    <input 
      v-model="articleUrl" 
      placeholder="Enter article URL"
      @keyup.enter="fetchArticle"
    />
    <button @click="fetchArticle">Fetch Article</button>

    <div v-if="loading" class="loader">Loading...</div>
    <div v-if="error" class="error">{{ error }}</div>

    <article v-if="article" class="article">
      <h1>{{ article.title }}</h1>
      <p class="meta">By: {{ article.authors.join(', ') }}</p>
      <img v-if="article.top_image" :src="article.top_image" alt="Featured" />
      <div class="content">{{ article.text }}</div>
      <div class="keywords">Tags: {{ article.keywords.join(', ') }}</div>
    </article>
  </div>
</template>

<script>
export default {
  data() {
    return {
      articleUrl: '',
      article: null,
      loading: false,
      error: null
    };
  },
  methods: {
    async fetchArticle() {
      this.loading = true;
      this.error = null;
      
      try {
        const response = await fetch(
          `https://web-production-7ff5.up.railway.app/scrape?url=${encodeURIComponent(this.articleUrl)}`
        );
        this.article = await response.json();
      } catch (err) {
        this.error = 'Failed to fetch article';
      } finally {
        this.loading = false;
      }
    }
  }
};
</script>
```

### 5. **Swift (iOS)**

```swift
import Foundation

class ArticleService {
    let baseURL = "https://web-production-7ff5.up.railway.app/scrape"
    
    func fetchArticle(url: String, completion: @escaping (Result<Article, Error>) -> Void) {
        guard let encodedURL = url.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed),
              let queryURL = URL(string: "\(baseURL)?url=\(encodedURL)") else {
            completion(.failure(NSError(domain: "Invalid URL", code: -1)))
            return
        }
        
        URLSession.shared.dataTask(with: queryURL) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }
            
            guard let data = data else {
                completion(.failure(NSError(domain: "No data", code: -1)))
                return
            }
            
            do {
                let article = try JSONDecoder().decode(Article.self, from: data)
                completion(.success(article))
            } catch {
                completion(.failure(error))
            }
        }.resume()
    }
}

struct Article: Codable {
    let title: String
    let authors: [String]
    let text: String
    let images: [String]
    let topImage: String
    let keywords: [String]
    let timestamp: String
    
    enum CodingKeys: String, CodingKey {
        case title, authors, text, images, keywords, timestamp
        case topImage = "top_image"
    }
}
```

***

## 🛡️ Best Practices

### 1. **URL Encoding**
Always properly encode the article URL before sending:
```javascript
const encodedUrl = encodeURIComponent(articleUrl);
```

### 2. **Error Handling**
```javascript
try {
  const response = await fetch(apiUrl);
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  const data = await response.json();
} catch (error) {
  console.error('Failed to fetch article:', error);
}
```

### 3. **Timeout Handling**
Set appropriate timeouts for requests:
```javascript
const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 seconds

try {
  const response = await fetch(apiUrl, { signal: controller.signal });
  // ...
} finally {
  clearTimeout(timeoutId);
}
```

### 4. **Rate Limiting**
Implement request throttling to avoid overwhelming the API:
```javascript
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

async function fetchMultipleArticles(urls) {
  for (const url of urls) {
    await getArticleData(url);
    await delay(1000); // Wait 1 second between requests
  }
}
```

***

## 📊 Supported News Sources

The API works with most modern news websites including:
- ✅ The Hindu
- ✅ BBC
- ✅ CNN
- ✅ Reuters
- ✅ AP News
- ✅ Guardian
- ✅ And most other news publications

***

## ⚠️ Limitations & Considerations

1. **CORS**: If using in browser-based apps, ensure CORS is properly configured
2. **Response Time**: Large articles may take 2-10 seconds to process
3. **Timeout**: Set client-side timeout to 30+ seconds
4. **URL Format**: Provide complete, valid article URLs
5. **Dynamic Content**: Articles with heavy JavaScript rendering may have incomplete content

***

## 🔧 Troubleshooting

### "Failed to fetch article"
- Check if the URL is valid and accessible
- Verify the article exists and isn't behind a paywall
- Ensure proper URL encoding

### "Timeout error"
- Increase timeout duration to 30+ seconds
- Check your internet connection
- The API might be processing a large article

### "Incomplete content"
- Some websites may require specific user-agents
- Dynamic content loaded via JavaScript may not be captured
- Try a different article source

***

## 📞 Support & Resources

- **GitHub Repository**: https://github.com/balarajakumara3-droid/article-scraper-api
- **Live API**: https://web-production-7ff5.up.railway.app/
- **Status**: Active and Running ✅

***

This documentation provides everything you need to integrate the article scraper API into any application!
