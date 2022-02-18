import {hsluvToHex} from 'hsluv'
import React from 'react'
import {useLocation} from 'react-router-dom'
import CreatableSelect from 'react-select/creatable'

import {ConfigContext} from './config'

// Sort an array of objects first by "order" and then by "name" attribute.
const cmp = (s, t) => s.order < t.order ? -1 : s.order > t.order ? 1 :
                      s.name < t.name ? -1 : s.name > t.name ? 1 : 0;


// Flatten the tags from an array of assets into a single Set.
const countTags = assets => {
  const counts = {};
  (assets || []).forEach(({tags}) => tags.forEach(t => {
    counts[t] = (counts[t] || 0) + 1;
  }));
  return counts;
}


const Group = ({icon, tags, clickHandler, className}) => {
  const path = useLocation().pathname;
  return <div key={icon} className={`tags ${className || ''}`}>
    <span className='icon'>{icon}</span>
    <ul>{tags.sort(cmp).map(t => {
      const active = path.indexOf(`/${t.name}/`) >= 0;
      return <li key={t.name}
                 className={`${t.group} ${active ? 'active' : ''}`}
                 style={{
                   background: hsluvToHex([t.hue, 100, 80]),
                   color: '#111',
                   cursor: clickHandler ? 'pointer' : 'default',
                 }}
                 onClick={clickHandler ? clickHandler(t) : null}>
        <span className='name'>{t.name}</span>
        <span className='count'>{t.count}</span>
      </li>;
    })}</ul>
  </div>;
}


const TagGroups = ({assets, className, hideEditable, clickHandler}) => {
  const assetIds = (assets || []).map(asset => asset.id).join('-');
  return <ConfigContext.Consumer>{config => {
    const groups = {}, icons = {}, counts = countTags(assets);
    config.tags.forEach(t => {
      if (t.count === 0) return;
      if (hideEditable && t.editable) return;
      if (assets && !counts[t.name]) return;
      if (!groups[t.group]) {
        icons[t.group] = t.icon;
        groups[t.group] = {name: t.group, order: t.order, tags: {}};
      }
      groups[t.group].tags[t.name] = t;
      if (assets) t.count = counts[t.name];
    });
    return Object.values(groups).sort(cmp).map(
      g => <Group key={`${g.name}-${assetIds}`}
                  icon={icons[g.name]}
                  tags={Object.values(g.tags)}
                  className={`${className || ''} ${g.name}`}
                  clickHandler={clickHandler} />
    );
  }}</ConfigContext.Consumer>;
}


const TagSelect = ({assets, className, refresh}) => {
  const update = asset => res => { asset.tags = res.tags; return res }
  const urlFor = (asset, tag) => `/asset/${asset.slug}/tags/${tag}/`
  const add = (a, tag) => fetch(urlFor(a, tag), { method: 'POST' }).then(res => res.json()).then(update(a))
  const tagToOption = t => ({label: t.name, value: t.name, color: hsluvToHex([t.hue, 100, 80])})

  const changeTags = (options, about) => {
    if (about.action === 'create-option') {
      const tag = options.slice(-1)[0].value
      const calls = assets.map(a => add(a, tag))
      Promise.all(calls).then(refresh)

    } else if (about.action === 'select-option') {
      const tag = options.slice(-1)[0].value
      assets.map(a => add(a, tag))

    } else if (about.action === 'pop-value' || about.action === 'remove-value') {
      const tag = about.removedValue.value;
      assets.map(a => fetch(urlFor(a, tag), {method: 'delete'}).then(res => res.json()).then(update(a)))
    }
  };

  return <ConfigContext.Consumer>{
    config => {
      const active = countTags(assets);
      return <CreatableSelect
               className={`${className || ''} tag-select`}
               key={assets.map(a => a.id).join('-') + Object.keys(active).join('-')}
               placeholder='Add tag...'
               isMulti
               isClearable={false}
               backspaceRemovesValue={false}
               onChange={changeTags}
               defaultValue={config.tags.filter(t => t.editable && active[t.name]).map(tagToOption)}
               options={config.tags.filter(t => t.editable).map(tagToOption)}
               styles={{
                 option: (base, {data, isFocused}) => ({
                   ...base,
                   background: isFocused ? '#eee' : data.color,
                   display: 'inline-block',
                   float: 'left',
                   width: 'auto',
                   margin: '0.2em',
                   padding: '0.2em 0.4em',
                   borderRadius: '3px',
                   cursor: 'pointer',
                 }),
                 control: base => ({...base, background: '#666', borderColor: '#666'}),
                 menu: base => ({...base, background: '#666'}),
                 multiValue: (base, {data}) => ({...base, background: data.color}),
                 multiValueLabel: base => ({...base, fontSize: '100%'}),
                 multiValueRemove: base => ({...base, fontSize: '100%'}),
                 placeholder: base => ({...base, color: '#111'}),
               }} />;
    }
  }</ConfigContext.Consumer>;
}

export {TagGroups, TagSelect}
