---
description: Quick product actions. Add, update, or delete products from the catalog.
agent: meta-expert
---

Manage products in the Butterfly catalog.

Without arguments: show product management menu.

With arguments:
- `/product add "Product Name" price currency` — create new product
- `/product update [ID] field value` — update product field
- `/product delete [ID]` — delete product (confirm first)
- `/product image [ID] [image_url]` — update product image
- `/product sets` — list all product sets
- `/product set [SET_ID]` — show products in a set

Catalog ID: `4394346397497710`

When adding products:
- Ask for: name, price, description, category
- Default currency: YER
- Default availability: in stock
- Brand: Butterfly
- Generate retailer_id: BUT-XXX format

Use these tools:
- `create_product` — add new product
- `update_product` — modify product
- `delete_product` — remove product
- `list_product_sets` — show collections
- `upload_image` — upload product image
