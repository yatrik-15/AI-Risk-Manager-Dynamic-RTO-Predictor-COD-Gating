FROM node:18-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy application code
COPY . .

# Expose port (Vite uses 5173 by default, but we configured it to 3000)
EXPOSE 3000

# Start development server (for demo purposes)
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
