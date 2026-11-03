"""On-demand official detail for a quake selected from the saved news stream."""
import re
import updates,weather,jma

def load(event_id):
 if not re.fullmatch(r'\d{14}',event_id):raise ValueError('Invalid event')
 def loader():
  import app
  catalog=weather.get_json('quake/data/list.json');rows=[r for r in catalog if updates.catalog_event_id(r)==event_id]
  if not rows:raise ValueError('This earthquake is outside the official publication window')
  import quake_revisions
  series=quake_revisions.series(rows);report=dict(series[-1]);report.update(id='catalog-'+event_id,provider='jma',history=list(reversed(series[:-1])),historyCount=len(series)-1)
  return {'report':report,'supplement':quake_revisions.supplement(report['reportId'])}
 return weather.cached('news-quake-detail45-'+event_id,60,loader)

def supplement(filename):
 import quake_revisions
 return quake_revisions.supplement(filename)
