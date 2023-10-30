import csv
import re
import urllib.parse
import urllib.request
from threading import Thread

from bs4 import BeautifulSoup

data = {}
country_dict = {
    'au': '.com.au',
    'at': '.at',
    'be': '.be',
    'ca': '.ca',
    'ch': '.ch',
    'de': '.de',
    'es': '.es',
    'fr': '.fr',
    'hk': '.com.hk',
    'ie': '.ie',
    'it': '.it',
    'my': '.com.my',
    'nl': '.nl',
    'ph': '.ph',
    'pl': '.pl',
    'sg': '.com.sg',
    'uk': '.co.uk',
    'us': '.com',
}
thread_list = []
condition_dict = {
    'all': '',
    'new': '&LH_ItemCondition=1000',
    'opened': '&LH_ItemCondition=1500',
    'refurbished': '&LH_ItemCondition=2500',
    'used': '&LH_ItemCondition=3000'
}

type_dict = {
    'all': '&LH_All=1',
    'auction': '&LH_Auction=1',
    'bin': '&LH_BIN=1',
    'offers': '&LH_BO=1'
}


def items(query, country='us', condition='all', item_type='all'):
    if country not in country_dict:
        raise Exception('Country not supported, please use one of the following: ' + ', '.join(country_dict.keys()))

    if condition not in condition_dict:
        raise Exception('Condition not supported, please use one of the following: ' + ', '.join(condition_dict.keys()))

    if item_type not in type_dict:
        raise Exception('Type not supported, please use one of the following: ' + ', '.join(type_dict.keys()))

    soup = get_html(query, country, condition, item_type, already_sold=False)
    data = parse_items(soup)

    return data


def average(query, country='us', condition='all'):
    if country not in country_dict:
        raise Exception('Country not supported, please use one of the following: ' + ', '.join(country_dict.keys()))

    if condition not in condition_dict:
        raise Exception('Condition not supported, please use one of the following: ' + ', '.join(condition_dict.keys()))

    soup = get_html(query, country, condition, item_type='all', already_sold=True)
    data = parse_prices(soup)

    avg_price = round(__average(data['price_list']), 2)
    avg_shipping = round(__average(data['shipping_list']), 2)

    return {
        'price': avg_price,
        'shipping': avg_shipping,
        'total': round(avg_price + avg_shipping, 2)
    }


def get_html(query, country, condition='', item_type='all', already_sold=True):
    already_sold_string = '&LH_Complete=1&LH_Sold=1' if already_sold else ''

    # Build the URL
    parsed_query = urllib.parse.quote(query).replace('%20', '+')
    url = f'https://www.ebay{country_dict[country]}/sch/i.html?_from=R40&_nkw=' + parsed_query + already_sold_string + \
          condition_dict[condition] + type_dict[item_type]

    # Get the web page HTML
    request = urllib.request.urlopen(url)
    soup = BeautifulSoup(request.read(), 'html.parser')

    return soup


def get_info_single_product(url):
    global data
    item_code = url[url.find('itm') + 4: url.find('?')]
    request = urllib.request.urlopen(url)
    soup = BeautifulSoup(request.read(), 'html.parser')

    seller_name_element = soup.find('h2', class_='d-stores-info-categories__container__info__section__title')
    seller_name = seller_name_element.get_text(strip=True) if seller_name_element else ""

    feedback_pr_elm = soup.find('div', {'class': 'd-stores-info-categories__container__info__section__item'})
    feedback_pr = feedback_pr_elm.get_text(strip=True) if feedback_pr_elm else "0"

    labels = [elm.get_text(strip=True) if elm else "" for elm in
              soup.findAll('div', {'class': 'fdbk-detail-seller-rating__label'})]
    values = [elm.get_text(strip=True) if elm else "0.0" for elm in
              soup.findAll('span', {'class': 'fdbk-detail-seller-rating__value'})]

    item_primary_price_elm = soup.find('div', {'class': 'x-price-primary'})
    item_primary_price = item_primary_price_elm.get_text(strip=True) if item_primary_price_elm else "0"

    item_approx_price_elm = soup.find('div', {'class': 'x-price-approx'})
    item_approx_price = item_approx_price_elm.get_text(strip=True) if item_approx_price_elm else "0"

    comment_elm = soup.findAll('div', {'class': 'fdbk-container__details__comment'})
    comment = "&".join(i.get_text(strip=True) for i in comment_elm) if comment_elm else "0"

    item_data = {
        'seller_name': seller_name,
        'feedback_pr': feedback_pr,
        'item_primary_price': ".".join(re.findall(r'[0-9]+', item_primary_price)),
        'item_approx_price': ".".join(re.findall(r'[0-9]+', item_approx_price, )),
        'comment': comment,
    }
    item_data.update({i: j for i, j in zip(labels, values)})
    data.setdefault(item_code, {}).update(item_data)


def parse_items(soup):
    global data
    raw_items = soup.find_all('div', {'class': 's-item__info clearfix'})

    for item in raw_items[1:]:

        # Get item data
        title = item.find(class_="s-item__title").find('span').get_text(strip=True)

        price = parse_raw_price(item.find('span', {'class': 's-item__price'}).get_text(strip=True))

        try:
            shipping = parse_raw_price(
                item.find('span', {'class': 's-item__shipping s-item__logisticsCost'}).find('span', {
                    'class': 'ITALIC'}).get_text(strip=True))
        except:
            shipping = 0

        try:
            time_left = item.find(class_="s-item__time-left").get_text(strip=True)
        except:
            time_left = ""

        try:
            time_end = item.find(class_="s-item__time-end").get_text(strip=True)
        except:
            time_end = ""

        try:
            bid_count = int(
                "".join(filter(str.isdigit, item.find(class_="s-item__bids s-item__bidCount").get_text(strip=True))))
        except:
            bid_count = 0

        try:
            review_count = int("".join(
                filter(str.isdigit, item.find(class_="s-item__reviews-count").find('span').get_text(strip=True))))
        except:
            review_count = 0

        url = item.find('a')['href']

        item_data = {
            'title': title,
            'price': price,
            'shipping': shipping,
            'time_left': time_left,
            'time_end': time_end,
            'bid_count': bid_count,
            'review_count': review_count,
            'url': url
        }

        data[url[url.find('itm') + 4: url.find('?')]] = item_data

        thread_list.append(Thread(target=get_info_single_product, args=(url,)))

    # Remove item with prices too high or too low
    # price_list = [item['price'] for item in data.values()]
    # parsed_price_list = st_dev_parse(price_list)
    # data = [item for item in data if item['price'] in parsed_price_list]
    #
    # return sorted(data, key=lambda dic: dic['price'] + dic['shipping'])
    return data


def parse_prices(soup):
    # Get item prices
    raw_price_list = [price.get_text(strip=True) for price in soup.find_all(class_="s-item__price")]
    price_list = [price for price in map(lambda raw_price: parse_raw_price(raw_price), raw_price_list) if price]

    # Get shipping prices
    raw_shipping_list = [item.get_text(strip=True) for item in
                         soup.find_all(class_="s-item__shipping s-item__logisticsCost")]
    shipping_list = map(lambda raw_price: parse_raw_price(raw_price), raw_shipping_list)
    shipping_list = [0 if price is None else price for price in shipping_list]

    # Remove prices too high or too low
    price_list = st_dev_parse(price_list)
    shipping_list = st_dev_parse(shipping_list)

    data = {
        'price_list': price_list,
        'shipping_list': shipping_list
    }
    return data


def parse_raw_price(string):
    parsed_price = re.search(r'(\d+(.\d+)?)', string.replace(',', '.'))
    if parsed_price:
        return float(parsed_price.group())
    return None


def __average(number_list):
    if len(list(number_list)) == 0: return 0
    return sum(number_list) / len(list(number_list))


def st_dev(number_list):
    if len(list(number_list)) == 0: return 0

    nominator = sum(map(lambda x: (x - sum(number_list) / len(number_list)) ** 2, number_list))
    st_deviation = (nominator / (len(number_list) - 1)) ** 0.5

    return st_deviation


def st_dev_parse(number_list):
    avg = __average(number_list)
    st_deviation = st_dev(number_list)

    # Remove prices too high or too low; Accept Between -1 StDev to +1 StDev
    number_list = [no for no in number_list if (avg + st_deviation > no > avg - st_deviation)]

    return number_list


# Unique or Vintage Items: These items are often one-off or secondhand designer pieces that attract a lot of
# attention and bids due to their uniqueness and rarity Health & Beauty: Products such as vitamins & dietary
# supplements, skincare products, perfume, hair straighteners, and hair dryers are among the best-selling items in
# this category Clothing: Specifically, women's jeans, men's t-shirts, and men's hats are among the top-selling items
# in the clothing category Electronics: Items like cables, computers, and mobile accessories are popular in this
# category Toys: This category is frequently bought, making it a popular choice for sellers Pet Supplies: This
# category is also among the most frequently bought items on eBay

product_list = [
    # 'vitamins and dietary supplements'
    # 'skincare products',
    # 'perfume',
    # 'hair straighteners',
    # 'hair dryers',
    # 'Electronics',
    # 'cables',
    # 'computers',
    # 'mobile accessories',
    # 'Toys',
    # 'Apple',
    # 'scanners',
    # 'Shoes',
    # 'Adidas',
    # 'Nike',
    # 'furniture',
    # 'Afghans',
    # 'Throw Blankets',
    # 'Afghans and Throw Blankets',
    # 'Pet Supplies',
    # 'Bookends',
    # 'Jewelry',
    # 'Watches',
    # 'Necklaces',
    # 'Pendants',
    # 'Wristwatch Bands',
    # 'Wristwatches',
    # 'sports memorabilia',
    # 'Historical Artifacts',
    # 'Automotive Parts',
    # 'Fashion',
    # 'Motors',
    # 'Collectibles',
    # 'Musical Instruments and Gear',
    # 'Motors',
]

main_threads = []
for product in product_list:
    # main_threads.append(Thread(target=items, args=(product, 'ca', 'all', 'offers')))
    items(query=product, country='ca', condition='all', item_type='offers')

for i in main_threads:
    i.start()

for i in main_threads:
    i.join()

for i in thread_list:
    i.start()

for i in thread_list:
    i.join()

# Specify the CSV file path
csv_file = 'output.csv'

# Write the dictionary to a CSV file
with open(csv_file, 'a', newline='') as csvfile:
    field_names = ['url', 'item_approx_price', 'Accurate description', 'price', 'time_left', 'seller_name',
                   'Communication', 'time_end', 'Shipping speed', 'title', 'shipping', 'bid_count', 'feedback_pr',
                   'item_primary_price', 'review_count', 'Reasonable shipping cost', 'item_no', 'comment']
    writer = csv.DictWriter(csvfile, fieldnames=field_names)
    writer.writeheader()  # Write the header row with field names
    for i, row in data.items():
        row['item_no'] = i
        writer.writerow(row)
