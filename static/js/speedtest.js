let stv = new Vue({
    el: "#speed",

    components: {
          apexchart: VueApexCharts
    },

    data: {
        ip: null,
        location: null,
        latency: null,
        received: null,
        node: null,
        stime: null,
        series: [
            {
                name: 'speed',
                type: 'area',
                data: []
            },
            {
                name: 'average',
                type: 'area',
                data: []
            }
        ],
        chartOptions: {
            chart: {
                height: "100%",
                type: 'area',
                toolbar: {
                    show: false
                },
                animations: {
                    enabled: false
                }
            },
            dataLabels: {
                enabled: false
            },
            stroke: {
                curve: 'smooth'
            },
            fill: {
                type: ['gradient', 'image']
            },
            xaxis: {
                type: "numeric",
                labels: {
                    formatter (val) {
                        return parseInt(val) + "s"
                    }
                },
            },
            yaxis: {
                labels: {
                    formatter: function(val, index){
                        return val + "Mbps"
                    }
                },
            },
        },
    },

    mounted () {
        axios
            .get("../netmeasuretmp/json/" + (new URLSearchParams(window.location.search)).get("json"))
            .then(response => {
                this.ip = response.data.ip
                this.location = response.data.location
                this.latency = response.data.latency
                this.received = response.data.received
                this.stime = response.data.time
                this.node = response.data.node
                for(let value of response.data.data){
                    this.series[0].data.push({
                        x: value["point"],
                        y: value["received"]
                    })
                    this.series[1].data.push({
                        x: value['point'],
                        y: response.data.average
                    })
                }
            })
            .catch(error => {
                console.log(error)
                this.errored = true
            })
            .finally(() => this.loading = false)
    }
})