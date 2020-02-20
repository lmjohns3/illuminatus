import React, {Component} from "react"
import {Link, useParams} from "react-router-dom"
import Select from "react-select"
import axios from "axios"

class View extends Component {
    render() {
        return <div className="view">VIEW {useParams().id}</div>
    }
}

export default View
