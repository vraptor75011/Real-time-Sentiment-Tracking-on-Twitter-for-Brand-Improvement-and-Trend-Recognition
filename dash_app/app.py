import dash
import dash_core_components as dcc
import dash_html_components as html
import pandas as pd
import plotly.graph_objs as go
import settings
import itertools
import math
import base64
from flask import Flask

import re
import nltk
nltk.download('punkt')
nltk.download('stopwords')
from nltk.probability import FreqDist
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from textblob import TextBlob


external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)


df = pd.read_csv('sample_data.csv')
df['created_at'] = pd.to_datetime(df['created_at'])

# Clean and transform data to enable time series
result = df.groupby([pd.Grouper(key='created_at', freq='2s'), 'polarity']).count().unstack(fill_value=0).stack().reset_index()
result = result.rename(columns={"id_str": "Num of '{}' mentions".format(settings.TRACK_WORDS[0]), "created_at":"Time in UTC"})  
time_series = result["Time in UTC"][result['polarity']==0].reset_index(drop=True)

# Clean and transform data to enable word frequency
content = ' '.join(df["text"])
content = re.sub(r"http\S+", "", content)
content = content.replace('RT ', ' ').replace('&amp;', 'and')
content = re.sub('[^A-Za-z0-9]+', ' ', content)
content = content.lower()

# Filter constants for states in US
STATES = ['Alabama', 'AL', 'Alaska', 'AK', 'American Samoa', 'AS', 'Arizona', 'AZ', 'Arkansas', 'AR', 'California', 'CA', 'Colorado', 'CO', 'Connecticut', 'CT', 'Delaware', 'DE', 'District of Columbia', 'DC', 'Federated States of Micronesia', 'FM', 'Florida', 'FL', 'Georgia', 'GA', 'Guam', 'GU', 'Hawaii', 'HI', 'Idaho', 'ID', 'Illinois', 'IL', 'Indiana', 'IN', 'Iowa', 'IA', 'Kansas', 'KS', 'Kentucky', 'KY', 'Louisiana', 'LA', 'Maine', 'ME', 'Marshall Islands', 'MH', 'Maryland', 'MD', 'Massachusetts', 'MA', 'Michigan', 'MI', 'Minnesota', 'MN', 'Mississippi', 'MS', 'Missouri', 'MO', 'Montana', 'MT', 'Nebraska', 'NE', 'Nevada', 'NV', 'New Hampshire', 'NH', 'New Jersey', 'NJ', 'New Mexico', 'NM', 'New York', 'NY', 'North Carolina', 'NC', 'North Dakota', 'ND', 'Northern Mariana Islands', 'MP', 'Ohio', 'OH', 'Oklahoma', 'OK', 'Oregon', 'OR', 'Palau', 'PW', 'Pennsylvania', 'PA', 'Puerto Rico', 'PR', 'Rhode Island', 'RI', 'South Carolina', 'SC', 'South Dakota', 'SD', 'Tennessee', 'TN', 'Texas', 'TX', 'Utah', 'UT', 'Vermont', 'VT', 'Virgin Islands', 'VI', 'Virginia', 'VA', 'Washington', 'WA', 'West Virginia', 'WV', 'Wisconsin', 'WI', 'Wyoming', 'WY']
STATE_DICT = dict(itertools.zip_longest(*[iter(STATES)] * 2, fillvalue=""))
INV_STATE_DICT = dict((v,k) for k,v in STATE_DICT.items())

# Clean and transform data to enable geo-distribution
is_in_US=[]
geo = df[['user_location']]
df = df.fillna(" ")
for x in df['user_location']:
    check = False
    for s in STATES:
        if s in x:
            is_in_US.append(STATE_DICT[s] if s in STATE_DICT else s)
            check = True
            break
    if not check:
        is_in_US.append(None)

geo_dist = pd.DataFrame(is_in_US, columns=['State']).dropna().reset_index()
geo_dist = geo_dist.groupby('State').count().rename(columns={"index": "Number"}) \
        .sort_values(by=['Number'], ascending=False).reset_index()
geo_dist["Log Num"] = geo_dist["Number"].apply(lambda x: math.log(x, 2))


geo_dist['Full State Name'] = geo_dist['State'].apply(lambda x: INV_STATE_DICT[x])
geo_dist['text'] = geo_dist['Full State Name'] + '<br>' + 'Num: ' + geo_dist['Number'].astype(str)


tokenized_word = word_tokenize(content)
stop_words=set(stopwords.words("english"))
filtered_sent=[]
for w in tokenized_word:
    if (w not in stop_words) and (len(w) >= 3):
        filtered_sent.append(w)
fdist = FreqDist(filtered_sent)
fd = pd.DataFrame(fdist.most_common(16), columns = ["Word","Frequency"]).drop([0]).reindex()
fd['Polarity'] = fd['Word'].apply(lambda x: TextBlob(x).sentiment.polarity)
fd['Marker_Color'] = fd['Polarity'].apply(lambda x: 'rgba(255, 50, 50, 0.6)' if x < -0.5 else \
        ('rgba(184, 247, 212, 0.6)' if x > 0.5 else 'rgba(131, 90, 241, 0.6)'))
fd['Line_Color'] = fd['Polarity'].apply(lambda x: 'rgba(255, 50, 50, 1)' if x < -0.5 else \
        ('rgba(184, 247, 212, 1)' if x > 0.5 else 'rgba(131, 90, 241, 1)'))
server = app.server

app.layout = html.Div(children=[
    html.H2('Real-time Twitter Sentiment Analysis for Brand Improvement and Topic Tracking', style={
        'textAlign': 'center'
    }),

    html.Div(children=[
        dcc.Graph(
            id='crossfilter-indicator-scatter',
            figure={
                'data': [
                    go.Scatter(
                        x=time_series,
                        y=result["Num of '{}' mentions".format(settings.TRACK_WORDS[0])][result['polarity']==0].reset_index(drop=True),
                        name="Neutrals",
                        opacity=0.8,
                        mode='lines',
                        line=dict(width=0.5, color='rgb(131, 90, 241)'),
                        stackgroup='one' 
                    ),
                    go.Scatter(
                        x=time_series,
                        y=result["Num of '{}' mentions".format(settings.TRACK_WORDS[0])][result['polarity']==-1].reset_index(drop=True).apply(lambda x: -x),
                        name="Negatives",
                        opacity=0.8,
                        mode='lines',
                        line=dict(width=0.5, color='rgb(255, 50, 50)'),
                        stackgroup='two' 
                    ),
                    go.Scatter(
                        x=time_series,
                        y=result["Num of '{}' mentions".format(settings.TRACK_WORDS[0])][result['polarity']==1].reset_index(drop=True),
                        name="Positives",
                        opacity=0.8,
                        mode='lines',
                        line=dict(width=0.5, color='rgb(184, 247, 212)'),
                        stackgroup='three' 
                    )
                ]
            }
        )
    ]),

    html.Div(children=[
        html.Div([
            dcc.Graph(
                id='x-time-series',
                figure = {
                    'data':[
                        go.Bar(                          
                            x=fd["Frequency"].loc[::-1],
                            y=fd["Word"].loc[::-1], 
                            name="Neutrals", 
                            orientation='h',
                            marker_color=fd['Marker_Color'].loc[::-1].to_list(),
                            marker=dict(
                                line=dict(
                                    color=fd['Line_Color'].loc[::-1].to_list(),
                                    width=1),
                                ),
                        )
                    ],
                    'layout':{
                        'hovermode':"closest"
                    }
                }        
            )
        ], style={'width': '49%', 'display': 'inline-block', 'padding': '0 20'}),
        html.Div([
            dcc.Graph(
                id='y-time-series',
                figure = {
                    'data':[
                        go.Choropleth(
                            locations=geo_dist['State'], # Spatial coordinates
                            z = geo_dist['Log Num'].astype(float), # Data to be color-coded
                            locationmode = 'USA-states', # set of locations match entries in `locations`
                            #colorscale = "Blues",
                            text=geo_dist['text'], # hover text
                            geo = 'geo',
                            colorbar_title = "Num in Log2",
                            marker_line_color='white',
                            colorscale = ["#fdf7ff", "#835af1"],
                            #autocolorscale=False,
                            #reversescale=True,
                        )
                    ],
                    'layout': {
                        'title': "Real-Time Tweet Geo-distribution".format(settings.TRACK_WORDS[0]),
                        'geo':{'scope':'usa'}
                    }
                }
            )
        ], style={'display': 'inline-block', 'width': '49%'})
    ]),


    # ABOUT ROW
    html.Div(
        className='row',
        children=[
            html.Div(
                className='three columns',
                children=[
                    html.P(
                    'Data extracted from:'
                    ),
                    html.A(
                        'Twitter API',
                        href='https://developer.twitter.com'
                    )                    
                ]
            ),
            html.Div(
                className='three columns',
                children=[
                    html.P(
                    'Code avaliable at:'
                    ),
                    html.A(
                        'GitHub',
                        href='https://github.com/Chulong-Li/Real-time-Sentiment-Tracking-on-Twitter-for-Brand-Improvement-and-Trend-Recognition'
                    )                    
                ]
            ),
            html.Div(
                className='three columns',
                children=[
                    html.P(
                    'Made with:'
                    ),
                    html.A(
                        'Dash / Plot.ly',
                        href='https://plot.ly/dash/'
                    )                    
                ]
            ),
            html.Div(
                className='three columns',
                children=[
                    html.P(
                    'Developer:'
                    ),
                    html.A(
                        'Chulong Li',
                        href='https://www.linkedin.com/in/chulong-li/'
                    )                    
                ]
            )                                                          
        ]
    )
], style={'padding': '20px'})


if __name__ == '__main__':
    app.run_server(debug=True)