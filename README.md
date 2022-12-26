# GitHub Issue Scraper

A Python-based scraper to download all issues and pull-requests from a GitHub repository.

Stores the issues and pull-requests as JSON files.

## Installation

```
pipx install git+https://github.com/agateau/ghi-scraper
```

## Usage

To avoid getting rate-limited: create a GitHub token (it only needs the "read repo" permission), store it in `$GITHUB_TOKEN`.

Run the scraper:

```
ghi-scraper user/repo where/to/store/the/files
```

If you plan to run this regularly, you can use the `--since` argument to reduce traffic and avoid getting rate-limited:

```
# Scrap since an absolute date
ghi-scraper user/repo where/to/store/the/files --since 2022-12-02

# Scrap all changes of the last 2 days
ghi-scraper user/repo where/to/store/the/files --since 2d

# Scrap all changes of the last 6 hours
ghi-scraper user/repo where/to/store/the/files --since 6h
```
