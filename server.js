// server.js
require('dotenv').config();
const express = require('express');
const axios = require('axios');
const cors = require('cors');

const app = express();
app.use(cors());
app.use(express.json());

const PORT = 8000;
const DISCOGS_TOKEN = process.env.DISCOGS_TOKEN; // Store this in a .env file

// Endpoint to fetch a specific user's collection
// server.js
app.get('/api/collection/:username', async (req, res) => {
    const { username } = req.params;
    try {
        const response = await axios.get(`https://api.discogs.com/users/${username}/collection/folders/0/releases`, {
            headers: {
                'Authorization': `Discogs token=${DISCOGS_TOKEN}`,
                'User-Agent': 'CrateDiggerApp/1.0'
            },
            params: {
                sort: 'added',
                sort_order: 'desc',
            }
        });
        // Send back the whole data object so the frontend can see the pagination info
        res.json(response.data);
    } catch (error) {
        res.status(error.response?.status || 500).json({ message: error.message });
    }
});

app.listen(PORT, () => console.log(`Backend running on http://localhost:${PORT}`)); 