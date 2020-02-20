import React, {Component} from "react"
import {Link, useParams} from "react-router-dom"
import Select from "react-select"
import axios from "axios"

class Browse extends Component {
    render() {
        return <div className="browse">BROWSE {useParams().query}</div>
    }
}

export default Browse
