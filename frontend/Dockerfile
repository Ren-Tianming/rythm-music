FROM node:22-alpine AS build

WORKDIR /app
ARG VITE_TURNSTILE_SITE_KEY
ARG VITE_TERMS_VERSION
ARG VITE_CSRF_COOKIE_NAME
ENV VITE_TURNSTILE_SITE_KEY=${VITE_TURNSTILE_SITE_KEY}
ENV VITE_TERMS_VERSION=${VITE_TERMS_VERSION}
ENV VITE_CSRF_COOKIE_NAME=${VITE_CSRF_COOKIE_NAME}
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
