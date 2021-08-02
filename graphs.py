import io

import matplotlib.pyplot as plt


def draw_goods_characteristics(column, row):
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.set_axis_off()

    goods_data = []

    for i in range(len(row)):
        goods_data.append([row[i], column[i]])

    collabel = ("Category", "Description")

    plt.table(
        cellText=goods_data,
        colLabels=collabel,
        colColours=["palegreen"] * len(row),
        loc='center'
    )
    fig.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    return buf


def draw_goods_comments(author, content, date):
    plt.figure()
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.set_axis_off()

    goods_data = []

    for i in range(len(date)):
        goods_data.append([author[i], content[i], date[i]])

    collabel = ("Author", "Content", "Date")

    table = plt.table(
        cellText=goods_data,
        colLabels=collabel,
        colColours=["palegreen"] * len(date),
        loc='center',
    )
    table.auto_set_font_size(False)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    return buf
