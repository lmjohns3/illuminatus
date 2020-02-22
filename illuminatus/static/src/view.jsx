import React from "react"
import {Link, useParams} from "react-router-dom"
import Select from "react-select"
import axios from "axios"

const View = () => (
    <div className="view">VIEW {useParams().id}</div>
)

export default View
